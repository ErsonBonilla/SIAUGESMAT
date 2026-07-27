import asyncio
import logging
import time
from typing import Dict, List

from celery import chord

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.moodle import MoodleIntegration
from app.repositories.execution_repo import (
    clear_checkpoint,
    get_checkpoint,
    get_execution,
    mark_completed,
    mark_failed,
    mark_running,
    save_checkpoint,
    set_report_dir,
    update_progress,
    _should_cancel,
    _should_pause,
)
from app.repositories.log_repo import save_error
from app.repositories.operation_repo import add_item, create_batch
from app.services.error_messages import translate_error
from app.services.etl import ETLService
from app.services.moodle import MoodleService
from app.services.reports import ReportService
from app.workers.etl_item_task import process_etl_item, _refresh_phase_progress
from app.workers.phase_common import (
    _acquire_advisory_lock,
    _get_pending_counts,
    _get_pending_items,
    _items_exist_for_execution,
    _launch_items_chord,
    _run_async,
    on_phase_items_done,
    on_users_done,
)
from app.workers.phase3_items import _create_phase3_items, _launch_delete_chord
from app.workers.phase4_items import _create_phase4_items
from app.workers.phases.base import PhaseContext, MoodleOverloadedError
from app.workers.phases.phase1_consult import ConsultPhase
from app.workers.phases.phase2_analyze import AnalyzePhase

logger = logging.getLogger(__name__)

PHASES = [ConsultPhase(), AnalyzePhase()]
PHASE_NAMES = ["1", "2"]
PROGRESS_START = [0, 20]
PROGRESS_RESTORE = [12, 30]


@celery_app.task(bind=True, autoretry_for=(MoodleOverloadedError,), max_retries=10,
                  default_retry_delay=60, retry_backoff=True, retry_backoff_max=600, retry_jitter=True,
                  soft_time_limit=25200, time_limit=28800)
def process_etl_file(self, execution_id: int, file_path: str, semester: str) -> None:
    db = SessionLocal()
    start_time = time.monotonic()
    execution = None

    try:
        execution = get_execution(db, execution_id)
        if not execution:
            logger.exception(f"No se encontró la ejecución {execution_id}")
            return

        if execution.status in ("cancelled", "paused", "review_required"):
            logger.info(f"Ejecución {execution_id} {execution.status}, no se procesa")
            return

        mark_running(db, execution_id)

        logger.info(f"Procesando archivo: {file_path}")
        etl_data = ETLService.process(file_path, execution.modalidad)

        moodle_config = settings.get_moodle_config(execution.modalidad or "")
        moodle_service = MoodleService(
            token=moodle_config["token"],
            base_url=moodle_config["url"],
            version=moodle_config["version"],
        )
        integration = MoodleIntegration(moodle_service)

        async def _run_phases() -> Dict[str, int]:
            try:
                return await _run_pipeline()
            finally:
                await moodle_service.close()

        async def _run_pipeline() -> Dict[str, int]:
            # Refrescar execution para PhaseContext
            current_exec = get_execution(db, execution_id) or execution
            ctx = PhaseContext(
                db=db,
                execution_id=execution_id,
                execution=current_exec,
                mode=current_exec.mode,
                semester=semester,
                etl_data=etl_data,
                moodle_service=moodle_service,
                integration=integration,
            )

            checkpoint = get_checkpoint(db, execution_id) or {}

            for i, phase in enumerate(PHASES):
                phase_name = PHASE_NAMES[i]

                if _should_cancel(db, execution_id):
                    update_progress(db, execution_id, PROGRESS_RESTORE[i - 1] if i > 0 else 12,
                                    f"FASE {phase_name} cancelada")
                    logger.info(f"FASE {phase_name}: cancelada por el usuario")
                    return ctx.metrics

                if _should_pause(db, execution_id):
                    update_progress(db, execution_id, PROGRESS_RESTORE[i - 1] if i > 0 else 12,
                                    f"FASE {phase_name} pausada")
                    logger.info(f"FASE {phase_name}: pausada por el usuario")
                    return ctx.metrics

                if phase_name in checkpoint:
                    _restore_checkpoint(ctx, checkpoint[phase_name], phase_name)
                    retry_count = _inc_retry_count(db, execution_id)
                    retry_label = f" (reintento {retry_count})" if retry_count > 0 else ""
                    update_progress(db, execution_id, PROGRESS_RESTORE[i],
                                    f"FASE {phase_name} restaurada desde checkpoint{retry_label}")
                    logger.info(f"FASE {phase_name}: restaurada desde checkpoint (reintento {retry_count})")
                else:
                    progress_key = f"{phase_name}_progress"
                    if progress_key in checkpoint:
                        _restore_progress_checkpoint(ctx, checkpoint[progress_key], phase_name)
                        logger.info(f"FASE {phase_name}: progreso parcial restaurado")
                    await phase.run(ctx)
                    _save_phase_checkpoint(db, execution_id, ctx, phase_name)
                    logger.info(f"FASE {phase_name}: completada, checkpoint guardado")

                    if phase_name == "2" and ctx.mode in ("courses", "both") and not _is_delete_confirmed(db, execution_id):
                        to_delete_count = len(ctx.comparison.get("to_delete", []))
                        if to_delete_count > settings.MAX_AUTO_DELETE_COURSES:
                            _require_review(db, execution_id, ctx)
                            return ctx.metrics

            return ctx.metrics

        metrics = _run_async(_run_phases())

        # Fresco: consultar estado actual de BD
        current_exec = get_execution(db, execution_id)

        if not current_exec:
            return

        if current_exec.status in ("cancelled", "paused"):
            logger.info(f"Ejecución {execution_id}: {current_exec.status} después de fases 1-2, no se lanza Fase 3")
            return

        if current_exec.status == "review_required":
            logger.info(f"Ejecución {execution_id}: en espera de confirmación de eliminación masiva")
            return

        if current_exec.status == "completed":
            logger.info(f"Ejecución {execution_id}: ya completada por chord callbacks, no se relanza")
            return

        # Save context for Phase 3 subtask orchestration
        phase2_data = get_checkpoint(db, execution_id) or {}
        _save_phase_2_data_to_checkpoint(db, execution_id, etl_data, metrics, phase2_data, current_exec.modalidad, current_exec.mode)

        update_progress(db, execution_id, 32, "Preparando subtareas…", step=3)
        logger.info(f"Ejecución {execution_id}: lanzando FASE 3 como subtareas")
        process_etl_phase.delay(execution_id, "3")

    except MoodleOverloadedError:
        raise
    except Exception as e:
        logger.exception(f"Error crítico en ejecución {execution_id}: {e}")
        try:
            db.rollback()
            if execution:
                save_error(db, execution_id, "critical", None, translate_error(e))
            mark_failed(db, execution_id, time.monotonic() - start_time)
        except Exception as db_error:
            logger.exception(f"No se pudo actualizar el estado fallido: {db_error}")
    finally:
        db.close()


def _save_phase_2_data_to_checkpoint(db, eid, etl_data, metrics, phase2_data, modalidad, mode):
    save_checkpoint(db, eid, "phase3_ctx", {
        "courses": etl_data.get("courses", []),
        "users": etl_data.get("users", []),
        "metrics": metrics,
        "modalidad": modalidad,
        "mode": mode,
        "comparison": phase2_data.get("2", {}).get("comparison", {}),
        "missing_categories": phase2_data.get("2", {}).get("missing_categories", []),
        "categories_to_relocate": phase2_data.get("2", {}).get("categories_to_relocate", []),
        "users_to_create": phase2_data.get("2", {}).get("users_to_create", []),
        "resolved_enrolments": phase2_data.get("2", {}).get("resolved_enrolments", []),
        "username_map": phase2_data.get("1", {}).get("username_map", {}),
    })


# ---------------------------------------------------------------------------
# Subtask orchestration: FASE 3 (Structure) and FASE 4 (People)
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, soft_time_limit=3600, time_limit=7200)
def process_etl_phase(self, execution_id: int, phase: str):
    db = SessionLocal()
    try:
        execution = get_execution(db, execution_id)
        if not execution:
            logger.error(f"Ejecución {execution_id} no encontrada para FASE {phase}")
            return
        if execution.status in ("paused", "cancelled"):
            logger.info(f"FASE {phase}: ejecución {execution.status}, no se lanzan subtareas")
            return

        phase3_ctx = get_checkpoint(db, execution_id) or {}
        ctx_data = phase3_ctx.get("phase3_ctx", {})
        comparison = ctx_data.get("comparison", {})
        modalidad = ctx_data.get("modalidad", execution.modalidad or "DISTANCIA")
        mode = ctx_data.get("mode", execution.mode or "both")

        def _do_courses():
            return mode in ("courses", "both")

        def _do_users():
            return mode in ("users", "both")

        if phase == "3":
            update_progress(db, execution_id, 34, "Preparando items de estructura…", step=3)

            # Categories inline (fast)
            if _do_courses() and ctx_data.get("missing_categories"):
                async def _create_cats():
                    moodle_config = settings.get_moodle_config(modalidad)
                    ms = MoodleService(token=moodle_config["token"], base_url=moodle_config["url"],
                                       version=moodle_config["version"])
                    try:
                        for cat in ctx_data["missing_categories"]:
                            existing = await ms.get_categories(idnumber=cat["idnumber"])
                            if existing:
                                logger.info(f"Categoría {cat['idnumber']} ya existe, omitiendo")
                                continue
                            await ms.create_categories([cat])
                    finally:
                        await ms.close()
                try:
                    asyncio.run(_create_cats())
                except Exception as e:
                    logger.exception(f"Error creando categorías: {e}")
                    save_error(db, execution_id, "3", None, translate_error(e))

            # Relocate categories with wrong parent
            cats_to_relocate = ctx_data.get("categories_to_relocate", [])
            if _do_courses() and cats_to_relocate:
                async def _relocate_cats():
                    moodle_config = settings.get_moodle_config(modalidad)
                    ms = MoodleService(token=moodle_config["token"], base_url=moodle_config["url"],
                                       version=moodle_config["version"])
                    integ = MoodleIntegration(ms)
                    try:
                        for cat in cats_to_relocate:
                            ok = await integ.relocate_category(
                                idnumber=cat["idnumber"],
                                moodle_id=cat["moodle_id"],
                                target_parent_idn=cat["expected_parent_idn"],
                            )
                            if ok:
                                logger.info(f"Categoría {cat['idnumber']} reubicada correctamente")
                    finally:
                        await ms.close()
                try:
                    asyncio.run(_relocate_cats())
                except Exception as e:
                    logger.exception(f"Error reubicando categorías: {e}")
                    save_error(db, execution_id, "3", None, translate_error(e))

            if not comparison:
                logger.info(f"FASE 3: sin datos de comparación, saltando")
                on_phase_items_done.delay(execution_id, "3")
                return

            update_progress(db, execution_id, 34, "Resolviendo templates y creando items…", step=3)
            item_counts = _create_phase3_items(db, execution_id, ctx_data, comparison, modalidad)
            total = sum(item_counts.values())
            if total == 0:
                logger.info(f"FASE 3: sin items que procesar")
                on_phase_items_done.delay(execution_id, "3")
                return

            # Delete items first, then structure items
            delete_items = _get_pending_items(db, execution_id, "3", "delete")
            structure_items = _get_pending_items(db, execution_id, "3", "structure")

            if delete_items:
                logger.info(f"FASE 3: lanzando {len(delete_items)} delete(s) + {len(structure_items)} estructura(s)")
                _launch_delete_chord(execution_id, delete_items)
            elif structure_items:
                _launch_items_chord(execution_id, structure_items)
            else:
                on_phase_items_done.delay(execution_id, "3")

        elif phase == "4":
            update_progress(db, execution_id, 65, "Creando items de personas…", step=4)
            item_counts = _create_phase4_items(db, execution_id, ctx_data, modalidad)
            total = sum(item_counts.values())
            if total == 0:
                logger.info(f"FASE 4: sin items que procesar")
                on_phase_items_done.delay(execution_id, "4")
                return

            # Secuencia: 1) crear usuarios, 2) enrolar profesores
            # Evita race condition donde enrol falla porque el usuario aun no existe
            user_items = _get_pending_items(db, execution_id, "4", sub_phase="create_user")
            enrol_items = _get_pending_items(db, execution_id, "4", sub_phase="enrol")

            if user_items:
                logger.info(f"FASE 4: creando {len(user_items)} usuario(s)")
                task_ids = [process_etl_item.si(item.id) for item in user_items]
                chord(task_ids)(on_users_done.s(
                    execution_id=execution_id,
                ))
            elif enrol_items:
                logger.info(f"FASE 4: enrolando {len(enrol_items)} profesor(es)")
                task_ids = [process_etl_item.si(item.id) for item in enrol_items]
                chord(task_ids)(on_phase_items_done.s(execution_id=execution_id, phase="4"))
            else:
                on_phase_items_done.delay(execution_id, "4")

    except Exception as e:
        logger.exception(f"Error en FASE {phase}: {e}")
        try:
            db.rollback()
            save_error(db, execution_id, "critical", None, translate_error(e))
            mark_failed(db, execution_id, 0)
        except Exception:
            pass
    finally:
        db.close()










# ---------------------------------------------------------------------------
# Helpers (preservados del original)
# ---------------------------------------------------------------------------

def _save_phase_checkpoint(db, eid, ctx: PhaseContext, phase_name: str):
    if phase_name == "1":
        save_checkpoint(db, eid, "1", {
            "cat_idnumbers": list(ctx.existing_cat_idnumbers),
            "courses": ctx.existing_courses,
            "username_map": ctx.username_map,
            "courses_with_teacher": dict(ctx.courses_with_teacher),
        })
    elif phase_name == "2":
        save_checkpoint(db, eid, "2", {
            "comparison": _serialize_comparison(ctx.comparison),
            "missing_categories": ctx.missing_categories,
            "categories_to_relocate": ctx.categories_to_relocate,
            "users_to_create": ctx.users_to_create,
            "resolved_enrolments": ctx.resolved_enrolments,
            "re_upload": ctx.re_upload,
        })


def _restore_checkpoint(ctx: PhaseContext, data: dict, phase_name: str):
    if phase_name == "1":
        ctx.existing_cat_idnumbers = set(data.get("cat_idnumbers", []))
        ctx.existing_courses = data.get("courses", [])
        ctx.username_map = data.get("username_map", {})
        ctx.courses_with_teacher = dict(data.get("courses_with_teacher", {}))
    elif phase_name == "2":
        ctx.comparison = data.get("comparison", {})
        ctx.missing_categories = data.get("missing_categories", [])
        ctx.categories_to_relocate = data.get("categories_to_relocate", [])
        ctx.users_to_create = data.get("users_to_create", [])
        ctx.resolved_enrolments = data.get("resolved_enrolments", [])
        ctx.re_upload = data.get("re_upload", False)


def _restore_progress_checkpoint(ctx: PhaseContext, data: dict, phase_name: str):
    ctx.metrics.update(data.get("metrics", {}))
    ctx.username_map.update(data.get("username_map", {}))


def _serialize_comparison(comparison: dict) -> dict:
    result = {}
    for k, v in comparison.items():
        if k == "logs":
            result[k] = v
        elif isinstance(v, set):
            result[k] = list(v)
        elif isinstance(v, list):
            result[k] = v
        else:
            result[k] = v
    return result


def _is_delete_confirmed(db, execution_id: int) -> bool:
    from app.db.models import Execution
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if not ex or not ex.phase_checkpoint:
        return False
    return ex.phase_checkpoint.get("delete_confirmed", False)


def _get_execution_status(db, execution_id: int) -> str:
    from app.db.models import Execution
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    return ex.status if ex else ""


def _require_review(db, execution_id: int, ctx):
    from app.db.models import Execution
    from sqlalchemy.orm.attributes import flag_modified
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if ex:
        to_delete_count = len(ctx.comparison.get("to_delete", []))
        ex.status = "review_required"
        ex.current_phase = f"Revisión requerida: {to_delete_count} cursos a eliminar"
        ex.progress_pct = 30
        ex.metrics = {
            **(ex.metrics or {}),
            "pending_delete_count": to_delete_count,
        }
        if ex.phase_checkpoint is None:
            ex.phase_checkpoint = {}
        ex.phase_checkpoint["delete_review"] = {
            "to_delete_count": to_delete_count,
            "to_create_count": len(ctx.comparison.get("to_create", [])),
            "threshold": settings.MAX_AUTO_DELETE_COURSES,
        }
        flag_modified(ex, "phase_checkpoint")
        db.commit()


def _inc_retry_count(db, execution_id: int) -> int:
    from app.db.models import Execution
    from sqlalchemy.orm.attributes import flag_modified
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if not ex:
        return 0
    if ex.phase_checkpoint is None:
        ex.phase_checkpoint = {}
    count = ex.phase_checkpoint.get("_retry_count", 0) + 1
    ex.phase_checkpoint["_retry_count"] = count
    flag_modified(ex, "phase_checkpoint")
    db.commit()
    return count
