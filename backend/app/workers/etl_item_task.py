import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.celery_app import celery_app
from app.core.config import settings
from app.core.logging_config import ExecutionContextFilter
from app.db.session import SessionLocal
from app.integrations.moodle import MoodleIntegration
from app.db.models import OperationItem
from app.repositories.execution_repo import _should_cancel, increment_metric
from app.repositories.log_repo import save_error, save_log
from app.repositories.operation_repo import get_item, update_item
from app.services.error_messages import translate_error
from app.services.moodle import MoodleOverloadedError, MoodleService, is_moodle_overloaded

logger = logging.getLogger(__name__)


# Cleanup items stuck in "processing" on worker start
def _reset_stuck_items():
    try:
        db = SessionLocal()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        stuck = db.query(OperationItem).filter(
            OperationItem.status == "processing",
            OperationItem.updated_at < cutoff,
        ).all()
        for item in stuck:
            item.status = "pending"
            item.error_message = "Reintentando tras timeout por crash"
        db.commit()
        if stuck:
            logger.info(f"Reseteados {len(stuck)} items stuck en 'processing'")
    except Exception:
        logger.exception("Error reseteando items stuck")
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

        if execution_id and _should_cancel(db, execution_id):
            update_item(db, item.id, "failed", "Ejecución cancelada")
            db.commit()
            return

        moodle_config = settings.get_moodle_config(modalidad)
        moodle = MoodleService(
            token=moodle_config["token"],
            base_url=moodle_config["url"],
            version=moodle_config["version"],
        )
        integration = MoodleIntegration(moodle)

        update_item(db, item.id, "processing")
        db.commit()

        async def _execute():
            success = False
            try:
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
                                 username, detail)
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
            finally:
                await moodle.close()

            if success:
                update_item(db, item.id, "completed")
                _log_success(db, execution_id, action, identifier, detail)
            else:
                error = integration.last_error or f"Error desconocido ({action}:{identifier})"
                update_item(db, item.id, "failed", error)
                _handle_error(execution_id, action, identifier, error, db=db)
            db.commit()
            _refresh_phase_progress(execution_id, db=db)

        try:
            asyncio.run(_execute())
        except MoodleOverloadedError:
            db.commit()
            raise
        except Exception as e:
            if is_moodle_overloaded(e):
                db.commit()
                raise MoodleOverloadedError(str(e)[:200])
            update_item(db, item.id, "failed", translate_error(e))
            _handle_error(execution_id, action, identifier, translate_error(e), db=db)
            db.commit()
            _refresh_phase_progress(execution_id, db=db)

    except MoodleOverloadedError:
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
    try:
        phase3_total = db.query(func.count(OperationItem.id)).filter(
            OperationItem.batch_id.like(f"etl_3_%_{execution_id}")
        ).scalar() or 0
        phase3_done = db.query(func.count(OperationItem.id)).filter(
            OperationItem.batch_id.like(f"etl_3_%_{execution_id}"),
            OperationItem.status.in_(["completed", "failed"]),
        ).scalar() or 0

        if phase3_total > 0 and phase3_done < phase3_total:
            pct = 34.0 + (phase3_done / phase3_total) * 28.0
        else:
            phase4_total = db.query(func.count(OperationItem.id)).filter(
                OperationItem.batch_id.like(f"etl_4_%_{execution_id}")
            ).scalar() or 0
            phase4_done = db.query(func.count(OperationItem.id)).filter(
                OperationItem.batch_id.like(f"etl_4_%_{execution_id}"),
                OperationItem.status.in_(["completed", "failed"]),
            ).scalar() or 0
            if phase4_total > 0:
                pct = 65.0 + (phase4_done / phase4_total) * 20.0
            else:
                total = phase3_total + phase4_total
                done = phase3_done + phase4_done
                pct = 34.0 + (done / max(total, 1)) * 28.0

        pct = round(pct, 1)
        ex = db.query(Execution).filter(Execution.id == execution_id).first()
        if ex and (ex.progress_pct is None or pct > ex.progress_pct):
            ex.progress_pct = pct
            ex.progress_updated_at = datetime.now(timezone.utc)
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
        log_detail = {"old_shortname": detail.get("old_shortname", "")}
    elif action == "enrol":
        log_detail = {"course": detail.get("course_shortname", "")}
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
        pass
    # Nota: No cerramos db porque la sesión pertenece al caller
