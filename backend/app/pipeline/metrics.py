"""Cálculo de métricas y semáforos ETL — transformaciones puras.

Los umbrales se reciben por parámetro (dict de floats), nunca se leen
settings ni la base de datos aquí.
"""

Thresholds = dict[str, float]

MESSAGES = {
    "red": "Se superaron umbrales críticos de error o duración.",
    "yellow": "Se superaron umbrales de advertencia.",
    "green": "Proceso exitoso.",
}


def calculate_error_rate(metrics: dict | None, errors_count: int | None) -> float:
    """Porcentaje de error de una ejecución.

    Si `metrics` no trae ``total_operations`` se estima sumando cursos,
    usuarios y matrículas creados. Devuelve 0.0 cuando no hay operaciones.
    """
    total = (
        (metrics or {}).get("total_operations", 0)
        or (
            (metrics or {}).get("courses_created", 0)
            + (metrics or {}).get("users_created", 0)
            + (metrics or {}).get("enrolments", 0)
        )
    )
    errors = errors_count or 0
    return (errors / total * 100.0) if total > 0 else 0.0


def semaphore_color(
    error_rate: float,
    duration: float,
    thresholds: Thresholds,
) -> str:
    """Color del semáforo según tasa de error y duración."""
    if error_rate >= thresholds["error_rate_red"] or duration >= thresholds["max_duration_red"]:
        return "red"
    if error_rate >= thresholds["error_rate_yellow"] or duration >= thresholds["max_duration_yellow"]:
        return "yellow"
    return "green"


def semaphore_message(color: str) -> str:
    """Mensaje descriptivo del color del semáforo."""
    return MESSAGES[color]
