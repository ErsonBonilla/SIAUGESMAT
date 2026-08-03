"""
Tareas periódicas de limpieza automática.

Ejecutadas por Celery Beat según el `beat_schedule` configurado
en `celery_app.py`. No se ejecutan bajo demanda.
"""

import logging
from datetime import datetime, timedelta, timezone

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Execution
from app.repositories.execution_repo import delete_old_pending_executions

logger = logging.getLogger(__name__)


@celery_app.task
def cleanup_pending_executions():
    """Elimina ejecuciones en estado 'pending' con más de 24 horas de antigüedad."""
    db = SessionLocal()
    try:
        deleted = delete_old_pending_executions(db, hours=24)
        if deleted:
            logger.info(f"Limpieza automática: {deleted} ejecuciones pending eliminadas")
    except Exception:
        logger.exception("Error en limpieza automática de ejecuciones pending")
        db.rollback()
    finally:
        db.close()


@celery_app.task
def cleanup_stuck_executions():
    """Marca como 'failed' ejecuciones 'running'/'queued' sin cambios por más de 6h."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc)
        stuck = db.query(Execution).filter(
            Execution.status.in_(["running", "queued"]),
        ).all()
        count = 0
        for ex in stuck:
            age = (cutoff - (ex.progress_updated_at or ex.started_at or ex.created_at)).total_seconds()
            if age > settings.STUCK_EXECUTION_TIMEOUT:
                ex.status = "failed"
                ex.current_phase = f"{ex.current_phase or ''} (timeout 6h)"
                ex.completed_at = cutoff
                ex.duration_seconds = round(age, 2)
                count += 1
        db.commit()
        if count:
            logger.info(f"Cleanup: {count} ejecuciones stuck marcadas como failed")
    except Exception:
        logger.exception("Error en limpieza de ejecuciones stuck")
        db.rollback()
    finally:
        db.close()


def _relaunch_phase4(db, eid: int) -> None:
    from app.workers.phases.common import (
        _get_pending_items,
        _mark_chord_active,
        on_phase_items_done,
        on_users_done,
    )
    from app.workers.phases.item_task import process_etl_item
    from celery import chord

    pending_users = _get_pending_items(db, eid, "4", sub_phase="create_user")
    if pending_users:
        task_ids = [process_etl_item.si(item.id) for item in pending_users]
        chord(task_ids)(on_users_done.s(execution_id=eid))
        _mark_chord_active(eid)
        return

    pending_enrols = _get_pending_items(db, eid, "4", sub_phase="enrol")
    if pending_enrols:
        task_ids = [process_etl_item.si(item.id) for item in pending_enrols]
        chord(task_ids)(on_phase_items_done.s(execution_id=eid, phase="4"))
        _mark_chord_active(eid)
        return

    on_phase_items_done.delay([], eid, "4")


@celery_app.task
def recover_stuck_phase():
    """Red de seguridad: relanza chords de FASE 3/4 atascados.

    Un chord puede quedar huérfano si un worker cae y su callback nunca se
    ejecuta. Esta tarea (programada por beat cada ~5 min):
    - Resetea items 'processing' viejos a 'pending' (incrementando intentos).
    - Si una fase tiene items pendientes, no tiene un chord activo vigente
      (marcador `chord_active` expirado/ausente) y no hay items procesándose
      recientemente, relanza el chord de la fase.
    """
    from app.workers.phases.common import _get_pending_items, _items_exist_for_execution
    from app.workers.phases.phase3_structure import on_delete_items_done
    from app.workers.utils import reset_stuck_items, STUCK_ITEM_TIMEOUT_MINUTES
    from app.db.models import OperationItem

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        executions = db.query(Execution).filter(Execution.status == "running").all()
        for ex in executions:
            eid = ex.id
            checkpoint = ex.phase_checkpoint or {}
            active_ts = checkpoint.get("chord_active")
            chord_alive = False
            if isinstance(active_ts, str):
                try:
                    chord_alive = datetime.fromisoformat(active_ts) > now
                except ValueError:
                    chord_alive = False

            if chord_alive:
                continue

            phase_relaunched = False
            for phase in ("3", "4"):
                pending = _get_pending_items(db, eid, phase)
                if not pending:
                    continue
                recent_processing = db.query(OperationItem).filter(
                    OperationItem.batch_id.like(f"etl_{phase}_%_{eid}"),
                    OperationItem.status == "processing",
                    OperationItem.updated_at >= now - timedelta(minutes=STUCK_ITEM_TIMEOUT_MINUTES),
                ).count()
                if recent_processing:
                    continue

                reset_stuck_items(
                    db, batch_id_prefix=f"etl_{phase}_%", execution_id=eid,
                    increment_attempt=True,
                )
                logger.warning(
                    f"Sweeper: fase {phase} de ejecución {eid} con {len(pending)} "
                    f"pendientes sin chord activo ni items recientes, relanzando"
                )
                if phase == "3":
                    on_delete_items_done.delay([], eid)
                else:
                    _relaunch_phase4(db, eid)
                phase_relaunched = True
                break

            if not phase_relaunched and not checkpoint.get("phase3_ctx"):
                has_items = _items_exist_for_execution(db, eid, "3") or _items_exist_for_execution(db, eid, "4")
                if not has_items:
                    heartbeat = ex.progress_updated_at or ex.created_at
                    stale = (
                        heartbeat is not None
                        and (now - heartbeat.replace(tzinfo=timezone.utc) if heartbeat.tzinfo is None else (now - heartbeat))
                        >= timedelta(minutes=STUCK_ITEM_TIMEOUT_MINUTES)
                    )
                    if stale:
                        retry = checkpoint.get("_retry_count", 0)
                        if retry < 3:
                            import os
                            file_path = os.path.join(settings.UPLOAD_DIR, ex.filename)
                            if os.path.isfile(file_path):
                                from app.workers.tasks import process_etl_file
                                checkpoint["_retry_count"] = retry + 1
                                ex.phase_checkpoint = checkpoint
                                db.commit()
                                logger.warning(
                                    f"Sweeper: ejecución {eid} atascada en fases 1-2 "
                                    f"(intento {retry + 1}/3), relanzando ETL"
                                )
                                process_etl_file.delay(ex.id, file_path, ex.semester)
    except Exception:
        logger.exception("Error en recuperación de fases atascadas")
        db.rollback()
    finally:
        db.close()
