import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from celery import chord
from sqlalchemy import text as sql_text

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import OperationItem
from app.repositories.execution_repo import (
    clear_checkpoint,
    get_execution,
    mark_completed,
    mark_failed,
    save_checkpoint,
    set_report_dir,
    update_progress,
)
from app.repositories.log_repo import save_error
from app.repositories.operation_repo import add_item, create_batch
from app.services.error_messages import translate_error
from app.services.moodle_operations import MoodleService
from app.services.reports import ReportService
from app.workers.phases.item_task import process_etl_item, _refresh_phase_progress
from app.workers.phases.base import PhaseContext, MoodleOverloadedError
from app.workers.utils import reset_stuck_items

logger = logging.getLogger(__name__)


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


def _acquire_advisory_lock(db, execution_id: int, phase: str) -> bool:
    key = f"etl_lock_{execution_id}_{phase}".encode()
    lock_id = int(hashlib.sha256(key).hexdigest(), 16) % (2**63)
    result = db.execute(
        sql_text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
        {"lock_id": lock_id},
    ).scalar()
    return bool(result)


def _items_exist_for_execution(db, execution_id, phase):
    return db.query(OperationItem).filter(
        OperationItem.batch_id.like(f"etl_{phase}_%_{execution_id}")
    ).first() is not None


def _get_pending_counts(db, execution_id: int, phase: str) -> Dict[str, int]:
    items = db.query(OperationItem).filter(
        OperationItem.batch_id.like(f"etl_{phase}_%_{execution_id}"),
        OperationItem.status == "pending",
    ).all()
    counts: Dict[str, int] = {}
    for item in items:
        action = (item.detail or {}).get("action", "unknown")
        counts[action] = counts.get(action, 0) + 1
    return counts


def _get_pending_items(db, execution_id, phase, sub_phase=None):
    query = db.query(OperationItem).filter(
        OperationItem.batch_id.like(f"etl_{phase}_%_{execution_id}"),
        OperationItem.status == "pending",
    )
    if sub_phase:
        if sub_phase == "structure":
            query = query.filter(sql_text("detail->>'action' != 'delete'"))
        else:
            query = query.filter(sql_text("detail->>'action' = :action")).params(action=sub_phase)
    return query.all()


def _launch_items_chord(execution_id, structure_items):
    if not structure_items:
        on_phase_items_done.delay(execution_id, "3")
        return
    task_ids = [process_etl_item.si(item.id) for item in structure_items]
    chord(task_ids)(on_phase_items_done.s(execution_id=execution_id, phase="3"))


@celery_app.task(bind=True, autoretry_for=(MoodleOverloadedError,), max_retries=3,
                  default_retry_delay=10, retry_backoff=True, retry_backoff_max=60)
def on_phase_items_done(self, results, execution_id, phase):
    _cb_entered = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        execution = get_execution(db, execution_id)
        if not execution or execution.status in ("paused", "cancelled"):
            return

        stuck = reset_stuck_items(
            db, batch_id_prefix=f"etl_{phase}_%", execution_id=execution_id, increment_attempt=True,
        )
        if stuck:
            logger.warning(f"FASE {phase}: {len(stuck)} items stuck reseteados a pending")

        if phase == "3":
            pending = _get_pending_items(db, execution_id, "3")
            if pending:
                logger.warning(f"FASE 3: {len(pending)} items pendientes tras chord, relanzando")
                _launch_items_chord(execution_id, pending)
                return
        elif phase == "4":
            pending = _get_pending_items(db, execution_id, "4")
            if pending:
                logger.warning(f"FASE 4: {len(pending)} items pendientes tras chord, relanzando")
                task_ids = [process_etl_item.si(item.id) for item in pending]
                chord(task_ids)(on_phase_items_done.s(execution_id=execution_id, phase="4"))
                return

        _sync_metrics_from_items(db, execution_id)

        if phase == "3":
            save_checkpoint(db, execution_id, "3", {"completed": True, "at": datetime.now(timezone.utc).isoformat()})
            update_progress(db, execution_id, 62, "FASE 3 completada, lanzando FASE 4", step=3)
            logger.info(f"FASE 3 completada para ejecución {execution_id}")
            celery_app.send_task("app.workers.phases.orchestrator.process_etl_phase", args=[execution_id, "4"])

        elif phase == "4":
            save_checkpoint(db, execution_id, "4", {"completed": True, "at": datetime.now(timezone.utc).isoformat()})
            update_progress(db, execution_id, 85, "Generando reportes…", step=5)
            report_ok = True
            try:
                report_dir = ReportService.generate_all(execution_id, db)
                set_report_dir(db, execution_id, report_dir)
                logger.info(f"Reportes generados en: {report_dir}")
            except Exception as e:
                logger.exception(f"Error generando reportes: {e}")
                save_error(db, execution_id, "critical", None, translate_error(e))
                report_ok = False

            update_progress(db, execution_id, 95, "Finalizando…")
            _cb_done = datetime.now(timezone.utc)
            metrics = execution.metrics or {}
            mark_completed(
                db, execution_id, metrics,
                errors_count=metrics.get("total_errors", 0),
                duration_seconds=(execution.started_at and (_cb_done - execution.started_at).total_seconds()) or 0,
            )
            clear_checkpoint(db, execution_id)
            update_progress(db, execution_id, 100, "Ejecución completada")
            logger.info(f"Ejecución {execution_id} completada {'' if report_ok else '(sin reportes)'}")

    except Exception as e:
        logger.exception(f"Error en on_phase_items_done (fase {phase}): {e}")
        try:
            db.rollback()
            save_error(db, execution_id, "critical", None, translate_error(e))
            mark_failed(db, execution_id, (datetime.now(timezone.utc) - _cb_entered).total_seconds() if execution.started_at else 0)
        except Exception:
            logger.exception(f"Error marcando fallido on_phase_items_done (fase {phase})")
    finally:
        db.close()


@celery_app.task(bind=True)
def on_users_done(self, results, execution_id):
    db = SessionLocal()
    try:
        failed_users = db.query(OperationItem).filter(
            OperationItem.batch_id.like(f"etl_4_users_%_{execution_id}"),
            OperationItem.status == "failed",
        ).all()
        if failed_users:
            failed_usernames = {item.identifier for item in failed_users}
            logger.warning(f"on_users_done: {len(failed_usernames)} usuario(s) no creados, "
                           f"marcando enrolments correspondientes como fallidos")
            enrol_to_fail = db.query(OperationItem).filter(
                OperationItem.batch_id.like(f"etl_4_enrol_%_{execution_id}"),
                OperationItem.status == "pending",
                OperationItem.identifier.in_(failed_usernames),
            ).all()
            for item in enrol_to_fail:
                item.status = "failed"
                item.error_message = "Usuario no pudo crearse en Moodle"
            if enrol_to_fail:
                db.commit()
                logger.info(f"Marcados {len(enrol_to_fail)} enrolments como failed por usuario no creado")

        enrol_items = _get_pending_items(db, execution_id, "4", sub_phase="enrol")
        if enrol_items:
            logger.info(f"on_users_done: enrolando {len(enrol_items)} profesor(es)")
            task_ids = [process_etl_item.si(item.id) for item in enrol_items]
            chord(task_ids)(on_phase_items_done.s(execution_id=execution_id, phase="4"))
        else:
            logger.info(f"on_users_done: sin enrolamientos pendientes")
            on_phase_items_done.delay(execution_id, "4")
    except Exception as e:
        logger.exception(f"Error en on_users_done: {e}")
        on_phase_items_done.delay(execution_id, "4")
    finally:
        db.close()


def _sync_metrics_from_items(db, execution_id):
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
        existing = ex.metrics or {}
        for key in metrics:
            existing[key] = metrics[key]
        ex.metrics = existing
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(ex, "metrics")
        db.commit()
