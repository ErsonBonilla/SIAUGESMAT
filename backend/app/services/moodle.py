"""Re-export del módulo moodle_operations para compatibilidad hacia atrás."""

from app.services.moodle_errors import MoodleAPIError, MoodleOverloadedError, _is_retryable_error, is_moodle_overloaded
from app.services.moodle_operations import MoodleService
from app.services.moodle_client import generate_moodle_password

__all__ = [
    "MoodleAPIError",
    "MoodleOverloadedError",
    "MoodleService",
    "generate_moodle_password",
    "is_moodle_overloaded",
    "_is_retryable_error",
]
