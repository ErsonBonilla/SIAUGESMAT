import logging
from typing import ClassVar

import httpx

logger = logging.getLogger(__name__)


class MoodleOverloadedError(Exception):
    """El servidor de Moodle está sobrecargado. Celery reintentará la tarea."""


def is_moodle_overloaded(e: BaseException) -> bool:
    """Retorna True si el error es transitorio (servidor sobrecargado, timeout, o errores DB de Moodle)."""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in (502, 503, 504)
    if isinstance(e, httpx.ConnectError):
        return True
    if isinstance(e, httpx.ReadTimeout):
        return True
    inner = e
    if hasattr(e, "last_attempt"):
        try:
            inner = e.last_attempt.exception() or inner
        except Exception:
            logger.debug("No se pudo obtener last_attempt.exception()")
    if isinstance(inner, MoodleAPIError) and inner.error_code in (
        "invalidrecord",
        "storedfilenotcreated",
        "invalidcoursemodule",
    ):
        return True
    msg = str(e).lower()
    return any(
        kw in msg
        for kw in ("gateway time-out", "connect error", "read timeout", "connection refused")
    )


def _is_retryable_error(exception: BaseException) -> bool:
    """Solo reintenta errores HTTP 5xx (servidor), errores de Moodle retryables
    y la sobrecarga transitoria de Moodle."""
    if isinstance(exception, MoodleOverloadedError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code >= 500
    if isinstance(exception, httpx.HTTPError):
        return True
    if isinstance(exception, MoodleAPIError):
        return exception.is_retryable
    return False


class MoodleAPIError(Exception):
    """Excepción lanzada cuando la API de Moodle devuelve un error."""

    NON_RETRYABLE_CODES = frozenset(
        {
            "invalidparameter",
            "missingparam",
            "invaliduser",
            "invalidcourse",
            "cannotcreatesitecourse",
            "invalidtoken",
            "nopermissions",
            "accessexception",
            "contextlevelnotsupported",
            "duplicatedshortname",
            "alreadyenrolled",
            "enrolmentnotfound",
            "notenrolled",
            "cannotdeletecategory",
            "cannotdeletecourse",
            "couldnotassignrole",
            "missingcapability",
            "duplicateuser",
            "duplicatecourse",
            "valueofparamelementnotset",
        }
    )

    ERROR_CODES: ClassVar[dict[str, str]] = {
        "invalidparameter": "Parámetro inválido enviado a Moodle.",
        "invalidtoken": "Token de autenticación inválido. Verifique la configuración.",
        "accessexception": "No tiene permisos para realizar esta operación en Moodle.",
        "nopermissions": "No tiene permisos para realizar esta operación en Moodle.",
        "requireloginerror": "Se requiere autenticación para acceder a este recurso en Moodle.",
        "course_not_found": "El curso no existe en Moodle.",
        "category_not_found": "La categoría no existe en Moodle.",
        "user_not_found": "El usuario no existe en Moodle.",
        "duplicatecourse": "Ya existe un curso con ese código en Moodle.",
        "wsfunctionnotavailable": "La función solicitada no está disponible en esta versión de Moodle.",
        "contextlevelnotsupported": "El nivel de contexto solicitado no es soportado por Moodle.",
        "missingparam": "Falta un parámetro requerido en la solicitud a Moodle.",
        "invalidrecord": "El registro solicitado no existe en Moodle.",
        "invalidcourse": "El curso especificado es inválido en Moodle.",
        "invaliduser": "El usuario especificado es inválido en Moodle.",
        "cannotcreatesitecourse": "No se puede crear un curso a nivel de sitio en Moodle.",
        "coursecategorynotfound": "La categoría de curso no existe en Moodle.",
        "enrol_cannot_usepregroup": "No se puede usar un grupo preexistente para esta matriculación.",
        "enrol_notenrollable": "El método de matriculación no está disponible en el curso.",
        "group_not_found": "El grupo no existe en Moodle.",
    }

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code

    @property
    def is_retryable(self) -> bool:
        return self.error_code not in self.NON_RETRYABLE_CODES

    @property
    def spanish_message(self) -> str:
        if self.error_code and self.error_code in self.ERROR_CODES:
            msg = self.ERROR_CODES[self.error_code]
        else:
            msg = str(self.args[0]) if self.args else "Error desconocido de Moodle."
        if self.error_code:
            return f"[{self.error_code}] {msg}"
        return msg

    def __str__(self):
        return self.spanish_message
