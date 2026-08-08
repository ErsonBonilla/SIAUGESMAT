"""Puente de orquestación entre la capa HTTP y Celery.

Los endpoints NO conocen Celery: encolan tareas y revocan mediante estas
funciones. Mantiene el transporte (broker, control) aislado en esta capa.
"""

import logging

from celery.result import AsyncResult

from app.celery_app import celery_app
from app.workers.operations_tasks import process_operation_batch
from app.workers.query_tasks import execute_query
from app.workers.tasks import process_etl_file

logger = logging.getLogger(__name__)


def enqueue_etl(execution_id: int, file_path: str, semester: str) -> AsyncResult:
    """Encola el procesamiento ETL de una ejecución."""
    return process_etl_file.delay(execution_id, file_path, semester)


def enqueue_async_query(task_id: str) -> None:
    """Encola una consulta asíncrona ya registrada en BD."""
    execute_query.delay(task_id)


def enqueue_operation_batch(batch_id: str) -> None:
    """Encola el procesamiento de un lote de operaciones (CSV masivo)."""
    process_operation_batch.delay(batch_id)


def revoke_task(task_id: str, terminate: bool = False) -> None:
    """Revoca una tarea Celery (pausa/cancelación)."""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
    except Exception as e:
        logger.warning(f"No se pudo revocar la tarea {task_id}: {e}")
