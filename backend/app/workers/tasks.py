import asyncio
import logging
import time
import uuid
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
    _should_pause,
)
from app.repositories.log_repo import save_error
from app.repositories.operation_repo import add_item, create_batch
from app.services.error_messages import translate_error
from app.services.etl import ETLService
from app.services.moodle import MoodleService
from app.services.reports import ReportService
from app.workers.etl_item_task import process_etl_item
from app.workers.phases.base import PhaseContext, MoodleOverloadedError
from app.workers.phases.phase1_consult import ConsultPhase
from app.workers.phases.phase2_analyze import AnalyzePhase

logger = logging.getLogger(__name__)

PHASES = [ConsultPhase(), AnalyzePhase()]
PHASE_NAMES = ["1", "2"]
PROGRESS_START = [0, 20]
PROGRESS_RESTORE = [12, 30]


@celery_app.task(bind=True, autoretry_for=(MoodleOverloadedError,), max_retries=10,
                  default_retry_delay=60, retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def process_etl_file(self, execution_id: int, file_path: str, semester: str) -> None:
    db = SessionLocal()
    start_time = time.monotonic()
    execution = None

    try:
        execution = get_execution(db, execution_id)
        if not execution:
            logger.exception(f"No se encontró la ejecución {execution_id}")
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
            ctx = PhaseContext(
                db=db,
                execution_id=execution_id,
                execution=execution,
                mode=execution.mode,
                semester=semester,
                etl_data=etl_data,
                moodle_service=moodle_service,
                integration=integration,
            )

            checkpoint = get_checkpoint(db, execution_id) or {}

            for i, phase in enumerate(PHASES):
                phase_name = PHASE_NAMES[i]

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

        metrics = asyncio.run(_run_phases())

        if _get_execution_status(db, execution_id) == "review_required":
            logger.info(f"Ejecución {execution_id}: en espera de confirmación de eliminación masiva")
            return

        # Check if Phase 3+ already done (completed from chord callbacks)
        if execution.status == "completed":
            return

        # Save context for Phase 3 subtask orchestration
        phase2_data = get_checkpoint(db, execution_id) or {}
        _save_phase_2_data_to_checkpoint(db, execution_id, etl_data, metrics, phase2_data, execution.modalidad, execution.mode)

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
                save_error(db, execution_id, "critical", "", translate_error(e))
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
        "users_to_create": phase2_data.get("2", {}).get("users_to_create", []),
        "resolved_enrolments": phase2_data.get("2", {}).get("resolved_enrolments", []),
        "username_map": phase2_data.get("1", {}).get("username_map", {}),
    })


# ---------------------------------------------------------------------------
# Subtask orchestration: FASE 3 (Structure) and FASE 4 (People)
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, soft_time_limit=300, time_limit=600)
def process_etl_phase(self, execution_id: int, phase: str):
    db = SessionLocal()
    try:
        execution = get_execution(db, execution_id)
        if not execution:
            logger.error(f"Ejecución {execution_id} no encontrada para FASE {phase}")
            return
        if execution.status == "paused":
            logger.info(f"FASE {phase}: ejecución pausada, no se lanzan subtareas")
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
            update_progress(db, execution_id, 34, "Creando categorías…", step=3)

            # Categories inline (fast)
            if _do_courses() and ctx_data.get("missing_categories"):
                async def _create_cats():
                    moodle_config = settings.get_moodle_config(modalidad)
                    ms = MoodleService(token=moodle_config["token"], base_url=moodle_config["url"],
                                       version=moodle_config["version"])
                    try:
                        for cat in ctx_data["missing_categories"]:
                            await ms.create_categories([cat])
                    finally:
                        await ms.close()
                try:
                    asyncio.run(_create_cats())
                except Exception as e:
                    logger.warning(f"Error creando categorías: {e}")

            if not comparison:
                logger.info(f"FASE 3: sin datos de comparación, saltando")
                on_phase_items_done.delay(execution_id, "3")
                return

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
                _launch_delete_chord(execution_id, delete_items, structure_items)
            elif structure_items:
                _launch_structure_chord(execution_id, structure_items)
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

            items = _get_pending_items(db, execution_id, "4")
            if items:
                logger.info(f"FASE 4: lanzando {len(items)} item(s)")
                task_ids = [process_etl_item.si(item.id) for item in items]
                chord(task_ids)(on_phase_items_done.s(execution_id=execution_id, phase="4"))
            else:
                on_phase_items_done.delay(execution_id, "4")

    except Exception as e:
        logger.exception(f"Error en FASE {phase}: {e}")
        try:
            db.rollback()
            save_error(db, execution_id, "critical", "", translate_error(e))
            mark_failed(db, execution_id, 0)
        except Exception:
            pass
    finally:
        db.close()


def _acquire_advisory_lock(db, execution_id: int, phase: str) -> bool:
    """Advisory lock por ejecución+fase vía pg_try_advisory_xact_lock.
    Retorna True si se obtuvo el lock, False si ya estaba tomado."""
    from sqlalchemy import text
    lock_id = hash((execution_id, phase)) % (2**63)
    result = db.execute(text("SELECT pg_try_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}).scalar()
    return bool(result)


def _items_exist_for_execution(db, execution_id, phase):
    from app.db.models import OperationItem
    return db.query(OperationItem).filter(
        OperationItem.batch_id.like(f"etl_{phase}_%_{execution_id}")
    ).first() is not None


def _create_phase3_items(db, execution_id, ctx_data, comparison, modalidad) -> Dict[str, int]:
    if _items_exist_for_execution(db, execution_id, "3"):
        logger.info(f"Items FASE 3 ya existen para ejecución {execution_id}, saltando creación")
        return {}
    if not _acquire_advisory_lock(db, execution_id, "3"):
        logger.info(f"Lock FASE 3 ya tomado para ejecución {execution_id}, otro worker crea los items")
        return {}

    counts: Dict[str, int] = {}
    courses = {c["shortname"]: c for c in ctx_data.get("courses", [])}

    def _batch_id(suffix):
        return f"etl_3_{suffix}_{execution_id}"

    def _add_items(identifiers, action, batch_suffix=None):
        if not identifiers:
            return
        batch_suffix = batch_suffix or action
        batch = create_batch(db, _batch_id(batch_suffix), "courses", action, len(identifiers), modalidad)
        count = 0
        for identifier in identifiers:
            detail = {"action": action, "execution_id": execution_id, "modalidad": modalidad}
            if isinstance(identifier, dict):
                detail.update({k: v for k, v in identifier.items() if k != "action"})
                identifier = identifier.get("shortname", identifier.get("identifier", str(identifier)))
            add_item(db, batch.batch_id, str(identifier), detail)
            count += 1
        counts[action] = count

    # Delete
    _add_items(comparison.get("to_delete", []), "delete")
    # Activate
    _add_items(comparison.get("to_activate", []), "activate")
    # Hide
    _add_items(comparison.get("to_hide", []), "hide")

    # Rename - needs old_shortname and fullname
    rename_items = comparison.get("to_update", [])
    if rename_items:
        batch = create_batch(db, _batch_id("rename"), "courses", "rename", len(rename_items), modalidad)
        count = 0
        for item in rename_items:
            sn = item["shortname"]
            course_data = courses.get(sn, {})
            detail = {
                "action": "rename", "execution_id": execution_id, "modalidad": modalidad,
                "old_shortname": item.get("old_shortname", sn),
                "fullname": course_data.get("fullname", sn),
            }
            add_item(db, batch.batch_id, sn, detail)
            count += 1
        counts["rename"] = count

    # Create - resolve template IDs upfront
    create_items = comparison.get("to_create", [])
    if create_items:
        _create_template_cache = {}

        async def _resolve_templates():
            moodle_config = settings.get_moodle_config(modalidad)
            ms = MoodleService(token=moodle_config["token"], base_url=moodle_config["url"],
                               version=moodle_config["version"])
            try:
                async def _resolve_single(item):
                    sn = item["shortname"]
                    course_data = courses.get(sn, {})
                    template = item.get("template_shortname") or course_data.get("templatecourse")
                    template_id = None
                    if template and template.startswith("PORTAFOLIO_"):
                        if template not in _create_template_cache:
                            try:
                                existing = await ms.get_courses(shortname=template)
                                _create_template_cache[template] = existing[0]["id"] if existing else None
                            except Exception:
                                _create_template_cache[template] = None
                        template_id = _create_template_cache.get(template)
                        if not template_id:
                            fallback = settings.DEFAULT_COURSE_TEMPLATE
                            if fallback not in _create_template_cache:
                                try:
                                    fb = await ms.get_courses(shortname=fallback)
                                    _create_template_cache[fallback] = fb[0]["id"] if fb else None
                                except Exception:
                                    _create_template_cache[fallback] = None
                            template_id = _create_template_cache.get(fallback)
                    return sn, course_data, template_id

                return await asyncio.gather(*[_resolve_single(item) for item in create_items])
            finally:
                await ms.close()

        try:
            resolved = asyncio.run(_resolve_templates())
        except Exception as e:
            logger.warning(f"Error resolviendo templates: {e}, se usarán sin template")
            resolved = [(item["shortname"], courses.get(item["shortname"], {}), None) for item in create_items]

        batch = create_batch(db, _batch_id("create"), "courses", "create", len(create_items), modalidad)
        count = 0
        for (sn, course_data, template_id) in resolved:
            detail = {
                "action": "create", "execution_id": execution_id, "modalidad": modalidad,
                "fullname": course_data.get("fullname", sn),
                "category_idnumber": course_data.get("category_idnumber", ""),
                "template_id": template_id,
            }
            add_item(db, batch.batch_id, sn, detail)
            count += 1
        counts["create"] = count

    db.commit()
    return counts


def _create_phase4_items(db, execution_id, ctx_data, modalidad) -> Dict[str, int]:
    if _items_exist_for_execution(db, execution_id, "4"):
        logger.info(f"Items FASE 4 ya existen para ejecución {execution_id}, saltando creación")
        return {}
    if not _acquire_advisory_lock(db, execution_id, "4"):
        logger.info(f"Lock FASE 4 ya tomado para ejecución {execution_id}, otro worker crea los items")
        return {}

    counts: Dict[str, int] = {}
    users_to_create = ctx_data.get("users_to_create", [])
    resolved_enrolments = ctx_data.get("resolved_enrolments", [])

    def _batch_id(suffix):
        return f"etl_4_{suffix}_{execution_id}"

    # Create users
    if users_to_create:
        batch = create_batch(db, _batch_id("users"), "users", "create", len(users_to_create), modalidad)
        count = 0
        for user in users_to_create:
            username = user.get("email", "").split("@")[0] if user.get("email") else user.get("username", str(uuid.uuid4()))
            detail = {
                "action": "create_user", "execution_id": execution_id, "modalidad": modalidad,
                "username": user.get("username", username),
                "firstname": user.get("firstname", ""),
                "lastname": user.get("lastname", ""),
                "email": user.get("email", ""),
                "password": user.get("password", ""),
                "cedula": user.get("cedula", ""),
                "city": user.get("city", ""),
                "description": user.get("description", ""),
                "email_personal": user.get("email_personal", ""),
            }
            identifier = user.get("username", username)
            add_item(db, batch.batch_id, identifier, detail)
            count += 1
        counts["create_users"] = count

    # Enrol teachers - resolve course_map upfront
    if resolved_enrolments:
        batch = create_batch(db, _batch_id("enrol"), "enrolments", "enrol", len(resolved_enrolments), modalidad)
        count = 0

        async def _resolve_course_map():
            moodle_config = settings.get_moodle_config(modalidad)
            ms = MoodleService(token=moodle_config["token"], base_url=moodle_config["url"],
                               version=moodle_config["version"])
            try:
                all_courses = await ms.get_courses()
                return {c["shortname"]: int(c["id"]) for c in all_courses if c.get("shortname")}
            finally:
                await ms.close()

        try:
            course_map = asyncio.run(_resolve_course_map())
        except Exception as e:
            logger.warning(f"Error resolviendo course_map para matriculas: {e}")
            course_map = {}

        for enrol in resolved_enrolments:
            username = enrol.get("username", "")
            course_sn = enrol.get("course_shortname", "")
            course_id = course_map.get(course_sn)  # resolve upfront
            detail = {
                "action": "enrol", "execution_id": execution_id, "modalidad": modalidad,
                "course_shortname": course_sn,
                "_course_id": course_id,
            }
            add_item(db, batch.batch_id, username, detail)
            count += 1
        counts["enrol"] = count

    db.commit()
    return counts


def _get_pending_items(db, execution_id, phase, sub_phase=None):
    from app.db.models import OperationItem
    query = db.query(OperationItem).filter(
        OperationItem.batch_id.like(f"etl_{phase}_%_{execution_id}"),
        OperationItem.status == "pending",
    )
    if sub_phase:
        from sqlalchemy import text as sql_text
        query = query.filter(sql_text("detail->>'action' = :action")).params(action=sub_phase)
    return query.all()


def _launch_delete_chord(execution_id, delete_items, structure_items):
    task_ids = [process_etl_item.si(item.id) for item in delete_items]
    chord(task_ids)(on_delete_items_done.s(execution_id=execution_id))


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=3,
                  default_retry_delay=10, retry_backoff=True, retry_backoff_max=60)
def on_delete_items_done(self, results, execution_id):
    """Callback cuando todos los deletes de FASE 3 completan.
    Consulta BD para obtener los items de estructura pendientes."""
    db = SessionLocal()
    try:
        execution = get_execution(db, execution_id)
        if not execution or execution.status == "paused":
            return

        update_progress(db, execution_id, 44, "Deletes completados, lanzando estructura…", step=3)
        structure_items = _get_pending_items(db, execution_id, "3", "structure")
        if structure_items:
            _launch_structure_chord(execution_id, structure_items)
        else:
            on_phase_items_done.delay(execution_id, "3")
    except Exception as e:
        logger.exception(f"Error en on_delete_items_done: {e}")
        raise
    finally:
        db.close()


def _launch_structure_chord(execution_id, structure_items):
    if not structure_items:
        on_phase_items_done.delay(execution_id, "3")
        return
    task_ids = [process_etl_item.si(item.id) for item in structure_items]
    chord(task_ids)(on_phase_items_done.s(execution_id=execution_id, phase="3"))


@celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=3,
                  default_retry_delay=10, retry_backoff=True, retry_backoff_max=60)
def on_phase_items_done(self, results, execution_id, phase):
    """Callback cuando todos los items de una fase completan."""
    db = SessionLocal()
    from datetime import datetime, timezone
    _cb_entered = datetime.now(timezone.utc)
    try:
        execution = get_execution(db, execution_id)
        if not execution:
            return

        # Update metrics from item results
        _sync_metrics_from_items(db, execution_id)

        if phase == "3":
            save_checkpoint(db, execution_id, "3", {"completed": True, "at": datetime.now(timezone.utc).isoformat()})
            update_progress(db, execution_id, 62, "FASE 3 completada, lanzando FASE 4", step=3)
            logger.info(f"FASE 3 completada para ejecución {execution_id}")
            process_etl_phase.delay(execution_id, "4")

        elif phase == "4":
            save_checkpoint(db, execution_id, "4", {"completed": True, "at": datetime.now(timezone.utc).isoformat()})

            # Phase 5: Reports (inline)
            update_progress(db, execution_id, 85, "Generando reportes…", step=5)
            report_ok = True
            try:
                report_dir = ReportService.generate_all(execution_id, db)
                set_report_dir(db, execution_id, report_dir)
                logger.info(f"Reportes generados en: {report_dir}")
            except Exception as e:
                logger.exception(f"Error generando reportes: {e}")
                save_error(db, execution_id, "critical", "", translate_error(e))
                report_ok = False

            update_progress(db, execution_id, 95, "Finalizando…")
            metrics = execution.metrics or {}
            mark_completed(
                db, execution_id, metrics,
                errors_count=metrics.get("total_errors", 0),
                duration_seconds=(execution.started_at and (_cb_entered - execution.started_at).total_seconds()) or 0,
            )
            clear_checkpoint(db, execution_id)
            update_progress(db, execution_id, 100, "Ejecución completada")
            logger.info(f"Ejecución {execution_id} completada {'' if report_ok else '(sin reportes)'}")

    except Exception as e:
        logger.exception(f"Error en on_phase_items_done (fase {phase}): {e}")
        try:
            db.rollback()
            save_error(db, execution_id, "critical", "", translate_error(e))
            mark_failed(db, execution_id, (datetime.now(timezone.utc) - _cb_entered).total_seconds())
        except Exception:
            pass
    finally:
        db.close()


def _sync_metrics_from_items(db, execution_id):
    """Reconstruye métricas desde los items completados/fallidos."""
    from app.db.models import OperationItem
    items = db.query(OperationItem).filter(
        OperationItem.batch_id.like(f"etl_%_{execution_id}")
    ).all()

    metrics = {
        "courses_deleted": 0, "courses_activated": 0, "courses_hidden": 0,
        "courses_renamed": 0, "courses_created": 0,
        "users_created": 0, "enrolments": 0, "enrolment_errors": 0,
        "total_errors": 0,
    }

    for item in items:
        action = (item.detail or {}).get("action", "")
        if item.status == "completed":
            key = {
                "delete": "courses_deleted", "activate": "courses_activated",
                "hide": "courses_hidden", "rename": "courses_renamed",
                "create": "courses_created", "create_user": "users_created",
                "enrol": "enrolments",
            }.get(action)
            if key:
                metrics[key] = metrics.get(key, 0) + 1
        elif item.status == "failed":
            if action == "enrol":
                metrics["enrolment_errors"] = metrics.get("enrolment_errors", 0) + 1
            metrics["total_errors"] = metrics.get("total_errors", 0) + 1

    ex = get_execution(db, execution_id)
    if ex:
        ex.metrics = metrics
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(ex, "metrics")
        db.commit()



# ---------------------------------------------------------------------------
# Helpers (preservados del original)
# ---------------------------------------------------------------------------

def _save_phase_checkpoint(db, eid, ctx: PhaseContext, phase_name: str):
    if phase_name == "1":
        save_checkpoint(db, eid, "1", {
            "cat_idnumbers": list(ctx.existing_cat_idnumbers),
            "courses": ctx.existing_courses,
            "username_map": ctx.username_map,
            "courses_with_teacher": list(ctx.courses_with_teacher),
        })
    elif phase_name == "2":
        save_checkpoint(db, eid, "2", {
            "comparison": _serialize_comparison(ctx.comparison),
            "missing_categories": ctx.missing_categories,
            "users_to_create": ctx.users_to_create,
            "resolved_enrolments": ctx.resolved_enrolments,
            "re_upload": ctx.re_upload,
        })


def _restore_checkpoint(ctx: PhaseContext, data: dict, phase_name: str):
    if phase_name == "1":
        ctx.existing_cat_idnumbers = set(data.get("cat_idnumbers", []))
        ctx.existing_courses = data.get("courses", [])
        ctx.username_map = data.get("username_map", {})
        ctx.courses_with_teacher = set(data.get("courses_with_teacher", []))
    elif phase_name == "2":
        ctx.comparison = data.get("comparison", {})
        ctx.missing_categories = data.get("missing_categories", [])
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
