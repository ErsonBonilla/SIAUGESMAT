"""
Módulo de cálculo de métricas y semáforos para procesos ETL.

Proporciona funciones que agregan datos de ejecuciones históricas,
calculan el estado del semáforo en base a umbrales configurables
y retornan el resumen de la última ejecución.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Execution
from app.schemas.analytics import (
    LatestExecution,
    SemesterMetrics,
    SemaphoreStatus,
)

logger = logging.getLogger(__name__)


def _get_semaphore_thresholds() -> Dict[str, float]:
    """Obtiene los umbrales configurables desde las variables de entorno."""
    return {
        "error_rate_yellow": settings.ANALYTICS_ERROR_THRESHOLD_YELLOW,
        "error_rate_red": settings.ANALYTICS_ERROR_THRESHOLD_RED,
        "max_duration_yellow": settings.ANALYTICS_MAX_DURATION_YELLOW,
        "max_duration_red": settings.ANALYTICS_MAX_DURATION_RED,
    }


def _calculate_error_rate(execution: Execution) -> float:
    """Calcula el porcentaje de error de una ejecución."""
    total = (
        (execution.metrics or {}).get("total_operations", 0)
        or (
            (execution.metrics or {}).get("courses_created", 0)
            + (execution.metrics or {}).get("users_created", 0)
            + (execution.metrics or {}).get("enrolments", 0)
        )
    )
    errors = execution.errors_count or 0
    return (errors / total * 100.0) if total > 0 else 0.0


def get_history_metrics(
    db: Session, limit: int = 10, modalidad: Optional[str] = None
) -> List[SemesterMetrics]:
    """
    Retorna una lista de métricas agregadas por semestre,
    ordenadas del más reciente al más antiguo.

    Args:
        db: Sesión de base de datos.
        limit: Número máximo de semestres a devolver.
        modalidad: Filtrar por modalidad (opcional).

    Returns:
        List[SemesterMetrics]: Lista con las métricas por semestre.
    """
    # Consulta base agrupada por semestre
    query = db.query(
        Execution.semester,
        func.count(Execution.id).label("total_executions"),
        func.sum(Execution.errors_count).label("total_errors"),
        func.avg(Execution.duration_seconds).label("avg_duration"),
        func.max(Execution.completed_at).label("last_completed"),
    )
    if modalidad:
        query = query.filter(Execution.modalidad == modalidad.upper())
    aggregate = (
        query
        .group_by(Execution.semester)
        .order_by(Execution.semester.desc())
        .limit(limit)
        .all()
    )

    if not aggregate:
        return []

    semesters = [row.semester for row in aggregate]

    # Obtener todas las ejecuciones de esos semestres para sumar métricas JSON
    detail_query = db.query(Execution).filter(Execution.semester.in_(semesters))
    if modalidad:
        detail_query = detail_query.filter(Execution.modalidad == modalidad.upper())
    executions = detail_query.all()

    # Agrupar ejecuciones por semestre
    grouped: Dict[str, List[Execution]] = {}
    for ex in executions:
        grouped.setdefault(ex.semester, []).append(ex)

    results: List[SemesterMetrics] = []
    for row in aggregate:
        semester = row.semester
        execs = grouped.get(semester, [])
        total_courses = 0
        total_users = 0
        total_enrolments = 0

        for ex in execs:
            metrics = ex.metrics or {}
            total_courses += metrics.get("courses_created", 0)
            total_users += metrics.get("users_created", 0)
            total_enrolments += metrics.get("enrolments", 0)

        avg_duration = round(row.avg_duration or 0.0, 2)

        results.append(
            SemesterMetrics(
                semester=semester,
                total_executions=row.total_executions,
                total_courses_created=total_courses,
                total_users_created=total_users,
                total_enrollments=total_enrolments,
                total_errors=row.total_errors or 0,
                avg_duration_seconds=avg_duration,
                last_completed=row.last_completed,
            )
        )

    return results


def get_semaphore_status(
    db: Session, semester: Optional[str] = None, modalidad: Optional[str] = None
) -> SemaphoreStatus:
    """
    Calcula el estado del semáforo para el último proceso completado
    del semestre especificado o del más reciente si no se indica.

    Args:
        db: Sesión de base de datos.
        semester: Semestre a consultar (opcional).
        modalidad: Filtrar por modalidad (opcional).

    Returns:
        SemaphoreStatus: Estado del semáforo con métricas y mensaje.
    """
    thresholds = _get_semaphore_thresholds()

    base_query = db.query(Execution).filter(Execution.status == "completed")
    if modalidad:
        base_query = base_query.filter(Execution.modalidad == modalidad.upper())

    if semester:
        execution = (
            base_query
            .filter(Execution.semester == semester)
            .order_by(Execution.completed_at.desc())
            .first()
        )
        if not execution:
            logger.warning(f"No se encontraron ejecuciones completadas para {semester}")
            return SemaphoreStatus(
                semester=semester,
                status="gray",
                error_rate=0.0,
                avg_duration=0.0,
                message=f"No hay ejecuciones completadas para {semester}.",
            )
    else:
        execution = (
            base_query
            .order_by(Execution.completed_at.desc())
            .first()
        )
        if not execution:
            return SemaphoreStatus(
                semester="N/A",
                status="gray",
                error_rate=0.0,
                avg_duration=0.0,
                message="No hay ejecuciones completadas aún.",
            )
        semester = execution.semester

    error_rate = _calculate_error_rate(execution)
    duration = execution.duration_seconds or 0.0

    # Determinar color del semáforo
    if error_rate >= thresholds["error_rate_red"] or duration >= thresholds["max_duration_red"]:
        color = "red"
        message = "Se superaron umbrales críticos de error o duración."
    elif error_rate >= thresholds["error_rate_yellow"] or duration >= thresholds["max_duration_yellow"]:
        color = "yellow"
        message = "Se superaron umbrales de advertencia."
    else:
        color = "green"
        message = "Proceso exitoso."

    return SemaphoreStatus(
        semester=semester,
        status=color,
        error_rate=round(error_rate, 2),
        avg_duration=round(duration, 2),
        message=message,
    )


def get_latest_execution_data(db: Session, modalidad: Optional[str] = None) -> LatestExecution:
    """
    Obtiene un resumen completo de la ejecución más reciente,
    incluyendo métricas y estado del semáforo.

    Args:
        db: Sesión de base de datos.
        modalidad: Filtrar por modalidad (opcional).

    Returns:
        LatestExecution: Datos de la última ejecución con indicadores.

    Raises:
        ValueError: Si no existen ejecuciones registradas.
    """
    query = db.query(Execution)
    if modalidad:
        query = query.filter(Execution.modalidad == modalidad.upper())
    execution = query.order_by(Execution.created_at.desc()).first()
    if not execution:
        raise ValueError("No hay ejecuciones registradas en la base de datos.")

    error_rate = _calculate_error_rate(execution)
    thresholds = _get_semaphore_thresholds()
    duration = execution.duration_seconds or 0.0

    if execution.status in ("queued", "running", "pending"):
        semaphore = "yellow"
    elif execution.status == "review_required":
        semaphore = "yellow"
    elif error_rate >= thresholds["error_rate_red"] or duration >= thresholds["max_duration_red"]:
        semaphore = "red"
    elif error_rate >= thresholds["error_rate_yellow"] or duration >= thresholds["max_duration_yellow"]:
        semaphore = "yellow"
    else:
        semaphore = "green"

    return LatestExecution(
        execution_id=execution.id,
        semester=execution.semester,
        filename=execution.filename,
        status=execution.status,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_seconds=execution.duration_seconds,
        metrics=execution.metrics,
        errors_count=execution.errors_count or 0,
        error_rate=round(error_rate, 2),
        semaphore=semaphore,
        moodle_version=execution.moodle_version,
        modalidad=execution.modalidad,
    )