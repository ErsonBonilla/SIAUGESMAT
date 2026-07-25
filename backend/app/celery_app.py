"""
Configuración de Celery para el procesamiento asíncrono de tareas ETL.

Define la aplicación Celery que se conecta a Redis como broker y
backend de resultados. Las tareas se auto-descubren mediante la
configuración ``imports`` (strings de módulo), evitando imports
eager en el nivel superior.
"""

import logging
import os

from celery import Celery
from celery.signals import after_setup_logger, task_failure

from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "siaugesmat",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    # Auto-descubrimiento de tareas (strings → evita imports eager)
    imports=(
        "app.workers.tasks",
        "app.workers.etl_item_task",
        "app.workers.cleanup_tasks",
        "app.workers.operations_tasks",
        "app.workers.query_tasks",
    ),

    # Seguimiento
    task_track_started=True,

    # Serialización
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Zona horaria
    timezone="America/Bogota",
    enable_utc=True,

    # Timeouts de tareas
    task_time_limit=settings.JOB_TIMEOUT,
    task_soft_time_limit=max(0, settings.JOB_TIMEOUT - 3600),

    # ACK tardío + visibilidad
    task_acks_late=True,
    broker_transport_options={
        "visibility_timeout": settings.JOB_TIMEOUT + 300,
        "global_keyprefix": "siaugesmat:",
        "retry_on_timeout": True,
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
    },

    # Resultados — expiran tras 1h para evitar llenar Redis
    task_ignore_result=True,
    result_expires=3600,

    # Pool de conexiones Redis
    redis_max_connections=20,
    broker_pool_limit=10,

    # Programación de tareas periódicas
    beat_schedule={
        "cleanup-pending-executions": {
            "task": "app.workers.cleanup_tasks.cleanup_pending_executions",
            "schedule": 21600.0,
        },
    },
)


# ---------------------------------------------------------------------------
# DLQ (Dead Letter Queue): captura tareas que agotaron reintentos
# ---------------------------------------------------------------------------
@after_setup_logger.connect
def setup_dlq_handler(logger, **kwargs):
    """Agrega un handler que registra tareas fallidas permanentemente."""
    dlq_logger = logging.getLogger("celery.dlq")
    dlq_logger.setLevel(logging.WARNING)
    handler = logging.FileHandler(os.path.join(settings.REPORT_DIR, "celery_dlq.log"))
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    ))
    dlq_logger.addHandler(handler)


@task_failure.connect
def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
    """Callback global cuando una tarea agota todos sus reintentos.
    Registra la tarea, sus argumentos y el error final en el logger DLQ."""
    dlq_logger = logging.getLogger("celery.dlq")
    dlq_logger.warning(
        "TASK_DLQ | task=%s task_id=%s args=%s kwargs=%s error=%s",
        sender.name, task_id, args, kwargs, exception,
    )
