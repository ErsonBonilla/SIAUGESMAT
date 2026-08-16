"""
Paquete de workers para tareas asíncronas (Celery).
"""

from app.workers.tareas import procesar_archivo_etl

__all__ = ["procesar_archivo_etl"]
