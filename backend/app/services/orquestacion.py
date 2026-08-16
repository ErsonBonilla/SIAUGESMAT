"""Puente de orquestación entre la capa HTTP y Celery.

Los endpoints NO conocen Celery: encolan tareas y revocan mediante estas
funciones. Mantiene el transporte (broker, control) aislado en esta capa.
"""

import logging

from celery.result import AsyncResult

from app.celery_app import celery_app
from app.workers.tareas import procesar_archivo_etl
from app.workers.tareas_consultas import ejecutar_consulta
from app.workers.tareas_operaciones import procesar_lote_operacion

logger = logging.getLogger(__name__)


def encolar_etl(execution_id: int, file_path: str, semester: str) -> AsyncResult:
    """Encola el procesamiento ETL de una ejecución."""
    return procesar_archivo_etl.delay(execution_id, file_path, semester)


def encolar_consulta_async(task_id: str) -> None:
    """Encola una consulta asíncrona ya registrada en BD."""
    ejecutar_consulta.delay(task_id)


def encolar_lote_operacion(batch_id: str) -> None:
    """Encola el procesamiento de un lote de operaciones (CSV masivo)."""
    procesar_lote_operacion.delay(batch_id)


def revocar_tarea(task_id: str, terminate: bool = False) -> None:
    """Revoca una tarea Celery (pausa/cancelación)."""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
    except Exception as e:
        logger.warning(f"No se pudo revocar la tarea {task_id}: {e}")
