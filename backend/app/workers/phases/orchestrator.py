import logging

from celery import chord

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.moodle import MoodleIntegration
from app.repositories.execution_repo import (
    get_checkpoint,
    get_execution,
    increment_metric,
    mark_failed,
    save_checkpoint,
    set_chord_active,
    update_progress,
)
from app.repositories.log_repo import save_error, save_log
from app.services.error_messages import translate_error
from app.services.moodle_factory import get_moodle_service
from app.workers.phases.base import PhaseContext
from app.workers.phases.common import (
    _get_pending_items,
    _launch_items_chord,
    on_phase_items_done,
    on_users_done,
)
from app.workers.phases.item_task import process_etl_item
from app.workers.phases.phase3_structure import (
    _create_phase3_items,
    _launch_delete_chord,
)
from app.workers.phases.phase4_people import _create_phase4_items
from app.workers.utils import _run_async

logger = logging.getLogger(__name__)


def _save_phase_2_data_to_checkpoint(db, eid, etl_data, metrics, phase2_data, modalidad, mode):
    save_checkpoint(db, eid, "phase3_ctx", {
        "courses": etl_data.get("courses", []),
        "users": etl_data.get("users", []),
        "existing_courses": phase2_data.get("1", {}).get("courses", []),
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

            if _do_courses() and ctx_data.get("missing_categories"):
                async def _create_cats():
                    ms = get_moodle_service(modalidad)
                    try:
                        for cat in ctx_data["missing_categories"]:
                            existing = await ms.get_categories(idnumber=cat["idnumber"])
                            if existing:
                                logger.info(f"Categoría {cat['idnumber']} ya existe, omitiendo")
                                continue
                            await ms.create_categories([cat])
                            save_log(db, execution_id, "3", "category_created", cat["idnumber"], {
                                "name": cat.get("name", ""),
                                "parent": cat.get("parent", ""),
                            })
                            increment_metric(db, execution_id, "categories_created")
                    finally:
                        await ms.close()
                try:
                    _run_async(_create_cats())
                except Exception as e:
                    logger.exception(f"Error creando categorías: {e}")
                    save_error(db, execution_id, "3", None, translate_error(e))

            cats_to_relocate = ctx_data.get("categories_to_relocate", [])
            if _do_courses() and cats_to_relocate:
                async def _relocate_cats():
                    ms = get_moodle_service(modalidad)
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
                    _run_async(_relocate_cats())
                except Exception as e:
                    logger.exception(f"Error reubicando categorías: {e}")
                    save_error(db, execution_id, "3", None, translate_error(e))

            if not comparison:
                logger.info("FASE 3: sin datos de comparación, saltando")
                on_phase_items_done.delay([], execution_id, "3")
                return

            update_progress(db, execution_id, 34, "Resolviendo templates y creando items…", step=3)
            item_counts = _create_phase3_items(db, execution_id, ctx_data, comparison, modalidad)
            total = sum(item_counts.values())
            if total == 0:
                logger.info("FASE 3: sin items que procesar")
                on_phase_items_done.delay([], execution_id, "3")
                return

            delete_items = _get_pending_items(db, execution_id, "3", "delete")
            structure_items = _get_pending_items(db, execution_id, "3", "structure")

            if delete_items:
                logger.info(f"FASE 3: lanzando {len(delete_items)} delete(s) + {len(structure_items)} estructura(s)")
                _launch_delete_chord(execution_id, delete_items)
            elif structure_items:
                _launch_items_chord(execution_id, structure_items)
            else:
                on_phase_items_done.delay([], execution_id, "3")

        elif phase == "4":
            update_progress(db, execution_id, 65, "Creando items de personas…", step=4)
            item_counts = _create_phase4_items(db, execution_id, ctx_data, modalidad)
            total = sum(item_counts.values())
            if total == 0:
                logger.info("FASE 4: sin items que procesar")
                on_phase_items_done.delay([], execution_id, "4")
                return

            user_items = _get_pending_items(db, execution_id, "4", sub_phase="create_user")
            enrol_items = _get_pending_items(db, execution_id, "4", sub_phase="enrol")

            if user_items:
                logger.info(f"FASE 4: creando {len(user_items)} usuario(s)")
                set_chord_active(db, execution_id)
                task_ids = [process_etl_item.si(item.id) for item in user_items]
                chord(task_ids)(on_users_done.s(
                    execution_id=execution_id,
                ))
            elif enrol_items:
                logger.info(f"FASE 4: enrolando {len(enrol_items)} profesor(es)")
                set_chord_active(db, execution_id)
                task_ids = [process_etl_item.si(item.id) for item in enrol_items]
                chord(task_ids)(on_phase_items_done.s(execution_id=execution_id, phase="4"))
            else:
                on_phase_items_done.delay([], execution_id, "4")

    except Exception as e:
        logger.exception(f"Error en FASE {phase}: {e}")
        try:
            db.rollback()
            save_error(db, execution_id, "critical", None, translate_error(e))
            mark_failed(db, execution_id, 0)
        except Exception:
            logger.exception("Error en rollback/error handling post-fallo de FASE {phase}")
    finally:
        db.close()


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
            continue
        if isinstance(v, set):
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


def _require_review(db, execution_id: int, ctx):
    from sqlalchemy.orm.attributes import flag_modified

    from app.db.models import Execution
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
    from sqlalchemy.orm.attributes import flag_modified

    from app.db.models import Execution
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
