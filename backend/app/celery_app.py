"""
Configuración de Celery para el procesamiento asíncrono de tareas ETL.

Define la aplicación Celery que se conecta a Redis como broker y
backend de resultados.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "siaugesmat",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Registrar tareas de todos los workers (Celery solo auto-descubre tasks.py)
import app.workers.cleanup_tasks     # noqa: registra cleanup_pending_executions
import app.workers.operations_tasks  # noqa: registra process_operation_batch
import app.workers.query_tasks      # noqa: registra execute_query
import app.workers.tasks            # noqa: registra process_etl_file

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bogota",
    enable_utc=True,
    task_time_limit=settings.JOB_TIMEOUT,
    task_soft_time_limit=settings.JOB_TIMEOUT - 3600,  # 1h de aviso antes del hard kill
    task_acks_late=True,
    broker_transport_options={"visibility_timeout": 3600},  # 1h, seguro con task_acks_late=True
    task_ignore_result=True,
    beat_schedule={
        "cleanup-pending-executions": {
            "task": "app.workers.cleanup_tasks.cleanup_pending_executions",
            "schedule": 21600.0,
        },
    },
)
