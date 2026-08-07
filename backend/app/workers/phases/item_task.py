import logging
from datetime import UTC, datetime

from sqlalchemy import func

from app.celery_app import celery_app
from app.core.logging_config import ExecutionContextFilter
from app.db.session import SessionLocal
from app.integrations.moodle import MoodleIntegration
from app.repositories.execution_repo import increment_metric, should_cancel
from app.repositories.log_repo import save_error, save_log
from app.repositories.operation_repo import claim_item, get_item, update_item
from app.services.error_messages import translate_error
from app.services.moodle_errors import MoodleOverloadedError, is_moodle_overloaded
from app.services.moodle_factory import get_moodle_service
from app.workers.utils import reset_stuck_items, run_moodle_async

logger = logging.getLogger(__name__)


# Cleanup items stuck in "processing" on worker start
def _reset_stuck_items():
    try:
        db = SessionLocal()
        reset_stuck_items(db)
    except Exception:
        logger.exception("Error reseteando items stuck en etl_item_task")
    finally:
        db.close()


_reset_stuck_items()


@celery_app.task(
    bind=True,
    autoretry_for=(MoodleOverloadedError,),
    max_retries=10,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    soft_time_limit=900,
    time_limit=1800,
)
def process_etl_item(self, item_id: int):
    db = SessionLocal()
    try:
        item = get_item(db, item_id)
        if not item:
            logger.error(f"Item {item_id} no encontrado")
            return
        if item.status == "completed":
            return

        detail = item.detail or {}
        action = detail.get("action")
        execution_id = detail.get("execution_id")
        modalidad = detail.get("modalidad", "DISTANCIA")
        identifier = item.identifier

        ExecutionContextFilter.set_context(
            execution_id=execution_id,
            item_id=item_id,
            action=action,
        )

        if not action:
            update_item(db, item.id, "failed", "Falta 'action' en detail")
            return

        if execution_id and should_cancel(db, execution_id):
            update_item(db, item.id, "failed", "Ejecución cancelada")
            db.commit()
            return

        moodle = get_moodle_service(modalidad)
        integration = MoodleIntegration(moodle)

        if not claim_item(db, item.id):
            return

        async def _execute():
            success = False
            if action == "delete":
                success = await integration.delete_course(identifier)
            elif action == "activate":
                success = await integration.activate_course(identifier)
            elif action == "hide":
                success = await integration.hide_course(identifier)
            elif action == "rename":
                success = await integration.rename_course(
                    old_shortname=detail.get("old_shortname", identifier),
                    new_shortname=identifier,
                    new_fullname=detail.get("fullname", ""),
                )
            elif action == "create":
                success = await integration.create_course(
                    shortname=identifier,
                    fullname=detail.get("fullname", ""),
                    category_idnumber=detail.get("category_idnumber", ""),
                    template_id=detail.get("template_id"),
                    recreate=detail.get("recreate", False),
                )
            elif action == "create_user":
                username, created = await integration.create_user_if_not_exists({
                    "username": identifier,
                    "firstname": detail.get("firstname", ""),
                    "lastname": detail.get("lastname", ""),
                    "email": detail.get("email", ""),
                    "password": detail.get("password", ""),
                    "cedula": detail.get("cedula", ""),
                    "city": detail.get("city", ""),
                    "description": detail.get("description", ""),
                })
                success = username is not None
                if success and created and execution_id:
                    save_log(db, execution_id, "4", "user_created_createpassword",
                             username, {**detail, "auth": "manual", "base_db": "Manual"})
            elif action == "enrol":
                course_id = detail.get("_course_id")
                course_map = {detail.get("course_shortname", ""): course_id} if course_id else None
                result = await integration.enrol_teacher(
                    username=identifier,
                    course_shortname=detail.get("course_shortname", ""),
                    course_map=course_map,
                )
                success = result["success"]
            else:
                update_item(db, item.id, "failed", f"Acción desconocida: {action}")
                db.commit()
                return

            if success:
                update_item(db, item.id, "completed")
                _log_success(db, execution_id, action, identifier, detail)
            else:
                error = integration.last_error or f"Error desconocido ({action}:{identifier})"
                if action == "enrol":
                    _log_enrol_failure(db, execution_id, identifier, detail, error)
                update_item(db, item.id, "failed", error)
                _handle_error(execution_id, action, identifier, error, db=db)
            db.commit()

        try:
            run_moodle_async(moodle, _execute())
        except MoodleOverloadedError:
            db.commit()
            raise
        except Exception as e:
            if is_moodle_overloaded(e):
                db.commit()
                raise MoodleOverloadedError(str(e)[:200]) from e
            update_item(db, item.id, "failed", translate_error(e))
            _handle_error(execution_id, action, identifier, translate_error(e), db=db)
            db.commit()

    except MoodleOverloadedError:
        if self.request.retries >= self.max_retries:
            error_msg = "Agotados reintentos por sobrecarga de Moodle"
            try:
                update_item(db, item.id, "failed", error_msg)
                if execution_id:
                    _handle_error(execution_id, action, identifier, error_msg, db=db)
                db.commit()
                logger.exception(
                    f"Item {item_id} marcado failed tras agotar reintentos por sobrecarga"
                )
            except Exception as exc:
                logger.exception(f"Error marcando failed item {item_id} tras sobrecarga: {exc}")
        else:
            raise
    except Exception as e:
        logger.exception(f"Error crítico en item {item_id}: {e}")
        try:
            db.rollback()
            if execution_id and item:
                update_item(db, item.id, "failed", translate_error(e))
                _handle_error(execution_id, action, identifier, translate_error(e), db=db)
                db.commit()
        except Exception as e:
            logger.exception(f"Error actualizando progreso para ejecución {execution_id}: {e}")
    finally:
        ExecutionContextFilter.clear_context()
        db.close()


def _refresh_phase_progress(execution_id, db):
    from app.db.models import Execution, OperationItem
    from app.pipeline.progress import compute_phase_progress
    try:
        phase3_total = db.query(func.count(OperationItem.id)).filter(
            OperationItem.batch_id.like(f"etl_3_%_{execution_id}")
        ).scalar() or 0
        phase3_done = db.query(func.count(OperationItem.id)).filter(
            OperationItem.batch_id.like(f"etl_3_%_{execution_id}"),
            OperationItem.status.in_(["completed", "failed"]),
        ).scalar() or 0

        phase4_total = db.query(func.count(OperationItem.id)).filter(
            OperationItem.batch_id.like(f"etl_4_%_{execution_id}")
        ).scalar() or 0
        phase4_done = db.query(func.count(OperationItem.id)).filter(
            OperationItem.batch_id.like(f"etl_4_%_{execution_id}"),
            OperationItem.status.in_(["completed", "failed"]),
        ).scalar() or 0

        pct = compute_phase_progress(
            phase3_total, phase3_done, phase4_total, phase4_done,
        )
        ex = db.query(Execution).filter(Execution.id == execution_id).first()
        if ex and (ex.progress_pct is None or pct > ex.progress_pct):
            ex.progress_pct = pct
            ex.progress_updated_at = datetime.now(UTC)
            db.commit()
    except Exception as e:
        logger.exception(f"Error actualizando progreso para ejecución {execution_id}: {e}")
    # Nota: No cerramos db porque la sesión pertenece al caller


def _log_success(db, execution_id, action, identifier, detail):
    if not execution_id:
        return
    phase = "3" if action in ("delete", "activate", "hide", "rename", "create") else "4"
    log_action = {
        "delete": "course_deleted",
        "activate": "course_activated",
        "hide": "course_hidden",
        "rename": "course_renamed",
        "create": "course_created",
        "create_user": "user_created",
        "enrol": "enrolment_ok",
    }.get(action, action)
    log_detail = {}
    if action == "rename":
        log_detail = {
            "old_shortname": detail.get("old_shortname", ""),
            "old_fullname": detail.get("old_fullname", ""),
            "new_fullname": detail.get("fullname", ""),
        }
    elif action == "enrol":
        log_detail = {
            "course": detail.get("course_shortname", ""),
            "fullname": detail.get("fullname", ""),
            "firstname": detail.get("firstname", ""),
            "lastname": detail.get("lastname", ""),
        }
    elif action in ("delete", "activate", "hide", "create"):
        for key in (
            "reason", "old_shortname", "old_professor", "professor",
            "template_shortname", "age_seconds", "recreate", "fullname",
            "category_idnumber", "firstname", "lastname",
        ):
            if key in detail:
                log_detail[key] = detail.get(key)
    if log_action != "user_created":
        save_log(db, execution_id, phase, log_action, identifier, log_detail)


def _handle_error(execution_id, action, identifier, error_msg, db):
    if not execution_id:
        return
    try:
        phase = "3" if action in ("delete", "activate", "hide", "rename", "create") else "4"
        save_error(db, execution_id, phase, identifier, error_msg)
        metric_key = "enrolment_errors" if action == "enrol" else "total_errors"
        increment_metric(db, execution_id, metric_key)
        if metric_key != "total_errors":
            increment_metric(db, execution_id, "total_errors")
    except Exception:
        logger.exception(f"Error manejando fallo ETL para {identifier}")
    # Nota: No cerramos db porque la sesión pertenece al caller


def _normalize_enrol_reason(error_msg: str) -> str:
    """Normaliza el motivo de un fallo de matriculación para el reporte.

    Los reportes inc_usuarios_inactivos y audit_matriculas esperan reasons
    como ``user_not_found``/``user_inactive``, pero los fallos llegan como
    mensajes en español o warningcodes de la API de Moodle.
    """
    m = (error_msg or "").lower()
    if "usuario no encontrado" in m or "user not found" in m:
        return "user_not_found"
    if "curso no encontrado" in m or "course not found" in m:
        return "course_not_found"
    if "inactive" in m or "suspendid" in m or "no activo" in m or "usernotactive" in m:
        return "user_inactive"
    if "alreadyenrolled" in m or "ya matriculado" in m:
        return "already_enrolled"
    return (error_msg or "").strip() or "unknown"


def _log_enrol_failure(db, execution_id, identifier, detail, error_msg):
    if not execution_id:
        return
    save_log(db, execution_id, "4", "enrolment_failed", identifier, {
        "course": detail.get("course_shortname", ""),
        "fullname": detail.get("fullname", ""),
        "reason": _normalize_enrol_reason(error_msg),
    })
