"""
Paquete de workers para tareas asíncronas (Celery).
"""

from app.workers.tasks import process_etl_file

__all__ = ["process_etl_file"]
