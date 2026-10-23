import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from app.services.errores_moodle import ErrorMoodleSobrecargado, es_moodle_sobrecargado

logger = logging.getLogger(__name__)


def extraer_error(e: Exception) -> str:
    if hasattr(e, "mensaje_espanol"):
        return e.mensaje_espanol
    if e.__cause__ and hasattr(e.__cause__, "mensaje_espanol"):
        return e.__cause__.mensaje_espanol
    if hasattr(e, "last_attempt"):
        try:
            inner = e.last_attempt.exception()
            if hasattr(inner, "mensaje_espanol"):
                return inner.mensaje_espanol
            msg = str(inner)[:300]
            return msg if msg.strip() else "Error sin mensaje específico del servidor"
        except Exception:
            pass
    msg = str(e)[:300]
    return msg if msg.strip() else "Error sin mensaje específico del servidor"


def manejar_errores_moodle(mensaje_log: str = "", retorno_por_defecto: Any = False) -> Callable:
    """Decorador que captura excepciones en métodos de MoodleIntegration,
    maneja errores de sobrecarga, registra el error y retorna un valor por defecto."""

    def decorador(funcion: Callable) -> Callable:
        @wraps(funcion)
        async def envoltorio(self, *args, **kwargs) -> Any:
            try:
                return await funcion(self, *args, **kwargs)
            except ErrorMoodleSobrecargado:
                raise
            except Exception as e:
                if es_moodle_sobrecargado(e):
                    raise ErrorMoodleSobrecargado(extraer_error(e)[:200]) from e
                self.ultimo_error = extraer_error(e)
                if mensaje_log:
                    logger.exception(mensaje_log)
                return retorno_por_defecto

        return envoltorio

    return decorador
