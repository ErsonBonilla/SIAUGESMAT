import logging
from functools import wraps
from typing import Any, Callable, Optional

from app.services.moodle_errors import MoodleOverloadedError, is_moodle_overloaded

logger = logging.getLogger(__name__)


def extract_error(e: Exception) -> str:
    if hasattr(e, 'spanish_message'):
        return e.spanish_message
    if e.__cause__ and hasattr(e.__cause__, 'spanish_message'):
        return e.__cause__.spanish_message
    if hasattr(e, 'last_attempt'):
        try:
            inner = e.last_attempt.exception()
            if hasattr(inner, 'spanish_message'):
                return inner.spanish_message
            msg = str(inner)[:300]
            return msg if msg.strip() else "Error sin mensaje específico del servidor"
        except Exception:
            pass
    msg = str(e)[:300]
    return msg if msg.strip() else "Error sin mensaje específico del servidor"


def handle_moodle_errors(log_message: str = "", default_return: Any = False) -> Callable:
    """Decorador que captura excepciones en métodos de MoodleIntegration,
    maneja errores de sobrecarga, registra el error y retorna un valor por defecto."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> Any:
            try:
                return await func(self, *args, **kwargs)
            except MoodleOverloadedError:
                raise
            except Exception as e:
                if is_moodle_overloaded(e):
                    raise MoodleOverloadedError(extract_error(e)[:200]) from e
                self.last_error = extract_error(e)
                if log_message:
                    logger.exception(log_message)
                return default_return
        return wrapper
    return decorator
