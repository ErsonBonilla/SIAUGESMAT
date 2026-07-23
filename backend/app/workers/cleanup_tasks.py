"""
Tareas periódicas de limpieza automática.

Ejecutadas por Celery Beat según el `beat_schedule` configurado
en `celery_app.py`. No se ejecutan bajo demanda.
"""

import logging

from app.celery_app import celery_app
from app.db.session import SessionLocal
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
