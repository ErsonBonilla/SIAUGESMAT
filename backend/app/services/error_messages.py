"""
Traducción de mensajes de error técnico a español descriptivo.

Mapea excepciones de Python, httpx, tenacity y MoodleAPI a mensajes
que un usuario administrador pueda entender sin ser programador.
"""

from app.services.moodle import MoodleAPIError


def translate_error(e: Exception) -> str:
    msg = str(e)

    # Errores de red / timeout
    if "ConnectError" in msg or "ConnectionError" in msg or "connection refused" in msg.lower():
        return ("Error de conexión a Moodle. Verifique que el servidor Moodle "
                "esté accesible y que tenga conexión a internet.")

    if "ReadTimeout" in msg or "Read timed out" in msg:
        return ("Tiempo de espera agotado al contactar Moodle. "
                "El servidor de Moodle está lento o no responde.")

    if "RetryError" in msg:
        return ("Agotados los reintentos de conexión a Moodle. "
                "Revise su conexión a internet y el estado del servidor Moodle.")

    if "HTTPStatusError" in msg or "Server error" in msg:
        return ("El servidor de Moodle devolvió un error HTTP. "
                "Posiblemente esté en mantenimiento o sobrecargado.")

    # Errores de Moodle API (ya tienen mensaje en español)
    if isinstance(e, MoodleAPIError):
        return e.spanish_message

    # Errores de validación / negocio (ya están en español en el código)
    if isinstance(e, ValueError):
        return str(e)

    # Fallback
    return f"Error inesperado: {str(e)[:300]}"
