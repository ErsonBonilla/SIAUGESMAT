"""
Configuración de logging estructurado en JSON para el backend.

Proporciona:
- JSONFormatter para logs legibles por máquina en producción
- ExecutionContextFilter para inyectar execution_id, item_id y action
  automáticamente en todos los LogRecord dentro del contexto de un worker
"""

import logging
import os
from contextvars import ContextVar
from typing import Optional

from pythonjsonlogger import jsonlogger

_context_vars: ContextVar[dict] = ContextVar("execution_context", default={})


class ExecutionContextFilter(logging.Filter):
    """Filtro que agrega execution_id, item_id y action a cada LogRecord.
    Los valores se toman de un ContextVar que debe establecerse al inicio
    de cada tarea Celery. Thread-safe (contextvars)."""

    @staticmethod
    def set_context(execution_id: Optional[int] = None,
                    item_id: Optional[int] = None,
                    action: Optional[str] = None,
                    phase: Optional[str] = None):
        _context_vars.set({
            "execution_id": execution_id,
            "item_id": item_id,
            "action": action,
            "phase": phase,
        })

    @staticmethod
    def clear_context():
        _context_vars.set({})

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in _context_vars.get().items():
            if value is not None:
                setattr(record, key, value)
        return True


class JSONFormatter(jsonlogger.JsonFormatter):
    """Formateador JSON con campos estándar y orden definido."""

    def __init__(self):
        super().__init__(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s",
            timestamp=True,
        )

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        if not log_record.get("timestamp"):
            log_record["timestamp"] = self.formatTime(record, self.datefmt)


def setup_logging(debug: bool = False):
    """Configura el logging global con formato JSON.
    En DEBUG usa formato texto plano para desarrollo."""
    root_logger = logging.getLogger()

    # Eliminar handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)

    if debug or os.getenv("DEV_LOGGING"):
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    else:
        formatter = JSONFormatter()

    handler.setFormatter(formatter)
    handler.addFilter(ExecutionContextFilter())
    root_logger.addHandler(handler)
