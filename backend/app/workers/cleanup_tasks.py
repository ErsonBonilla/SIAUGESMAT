"""
Tareas periódicas de limpieza automática.

Ejecutadas por Celery Beat según el `beat_schedule` configurado
en `celery_app.py`. No se ejecutan bajo demanda.
"""

import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models import Execution
from app.repositories.execution_repo import delete_old_pending_executions, mark_failed

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
            if age > 21600:  # 6 horas
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
