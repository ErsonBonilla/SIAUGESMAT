"""
Módulo de cálculo de métricas y semáforos para procesos ETL.

Proporciona funciones que agregan datos de ejecuciones históricas,
calculan el estado del semáforo en base a umbrales configurables
y retornan el resumen de la última ejecución.
"""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.modelos import Ejecucion
from app.pipeline.metricas import (
    calcular_tasa_error,
    color_semaforo,
    mensaje_semaforo,
)
from app.schemas.analitica import (
    EjecucionReciente,
    EstadoSemaforo,
    MetricasSemestre,
)

logger = logging.getLogger(__name__)


def _obtener_umbrales_semaforo() -> dict[str, float]:
    """Obtiene los umbrales configurables desde las variables de entorno."""
    return {
        "error_rate_yellow": settings.ANALYTICS_ERROR_THRESHOLD_YELLOW,
        "error_rate_red": settings.ANALYTICS_ERROR_THRESHOLD_RED,
        "max_duration_yellow": settings.ANALYTICS_MAX_DURATION_YELLOW,
        "max_duration_red": settings.ANALYTICS_MAX_DURATION_RED,
    }


def obtener_metricas_historial(
    db: Session, limit: int = 10, modalidad: str | None = None
) -> list[MetricasSemestre]:
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
        Ejecucion.semestre,
        func.count(Ejecucion.id).label("total_executions"),
        func.sum(Ejecucion.conteo_errores).label("total_errors"),
        func.avg(Ejecucion.duracion_segundos).label("avg_duration"),
        func.max(Ejecucion.completado_en).label("last_completed"),
    )
    if modalidad:
        query = query.filter(Ejecucion.modalidad == modalidad.upper())
    aggregate = (
        query.group_by(Ejecucion.semestre).order_by(Ejecucion.semestre.desc()).limit(limit).all()
    )

    if not aggregate:
        return []

    semesters = [row.semestre for row in aggregate]

    # Obtener todas las ejecuciones de esos semestres para sumar métricas JSON
    detail_query = db.query(Ejecucion).filter(Ejecucion.semestre.in_(semesters))
    if modalidad:
        detail_query = detail_query.filter(Ejecucion.modalidad == modalidad.upper())
    executions = detail_query.all()

    # Agrupar ejecuciones por semestre
    grouped: dict[str, list[Ejecucion]] = {}
    for ex in executions:
        grouped.setdefault(ex.semestre, []).append(ex)

    results: list[MetricasSemestre] = []
    for row in aggregate:
        semester = row.semestre
        execs = grouped.get(semester, [])
        total_courses = 0
        total_users = 0
        total_enrolments = 0

        for ex in execs:
            metrics = ex.metricas or {}
            total_courses += metrics.get("courses_created", 0)
            total_users += metrics.get("users_created", 0)
            total_enrolments += metrics.get("enrolments", 0)

        avg_duration = round(row.avg_duration or 0.0, 2)

        results.append(
            MetricasSemestre(
                semestre=semester,
                total_ejecuciones=row.total_executions,
                total_cursos_creados=total_courses,
                total_usuarios_creados=total_users,
                total_matriculaciones=total_enrolments,
                total_errores=row.total_errors or 0,
                duracion_promedio_segundos=avg_duration,
                ultima_completada=row.last_completed,
            )
        )

    return results


def obtener_estado_semaforo(
    db: Session, semester: str | None = None, modalidad: str | None = None
) -> EstadoSemaforo:
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
    thresholds = _obtener_umbrales_semaforo()

    base_query = db.query(Ejecucion).filter(Ejecucion.estado == "completed")
    if modalidad:
        base_query = base_query.filter(Ejecucion.modalidad == modalidad.upper())

    if semester:
        execution = (
            base_query.filter(Ejecucion.semestre == semester)
            .order_by(Ejecucion.completado_en.desc())
            .first()
        )
        if not execution:
            logger.warning(f"No se encontraron ejecuciones completadas para {semester}")
            return EstadoSemaforo(
                semestre=semester,
                estado="gray",
                tasa_error=0.0,
                duracion_promedio=0.0,
                mensaje=f"No hay ejecuciones completadas para {semester}.",
            )
    else:
        execution = base_query.order_by(Ejecucion.completado_en.desc()).first()
        if not execution:
            return EstadoSemaforo(
                semestre="N/A",
                estado="gray",
                tasa_error=0.0,
                duracion_promedio=0.0,
                mensaje="No hay ejecuciones completadas aún.",
            )
        semester = execution.semestre

    error_rate = calcular_tasa_error(execution.metricas, execution.conteo_errores)
    duration = execution.duracion_segundos or 0.0

    color = color_semaforo(error_rate, duration, thresholds)
    message = mensaje_semaforo(color)

    return EstadoSemaforo(
        semestre=semester,
        estado=color,
        tasa_error=round(error_rate, 2),
        duracion_promedio=round(duration, 2),
        mensaje=message,
    )


def obtener_datos_ejecucion_reciente(
    db: Session, modalidad: str | None = None
) -> EjecucionReciente:
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
    query = db.query(Ejecucion)
    if modalidad:
        query = query.filter(Ejecucion.modalidad == modalidad.upper())
    execution = query.order_by(Ejecucion.creado_en.desc()).first()
    if not execution:
        raise ValueError("No hay ejecuciones registradas en la base de datos.")

    error_rate = calcular_tasa_error(execution.metricas, execution.conteo_errores)
    thresholds = _obtener_umbrales_semaforo()
    duration = execution.duracion_segundos or 0.0

    if execution.estado in ("queued", "running", "pending", "review_required"):
        semaphore = "yellow"
    else:
        semaphore = color_semaforo(error_rate, duration, thresholds)

    return EjecucionReciente(
        id=execution.id,
        semestre=execution.semestre,
        nombre_archivo=execution.nombre_archivo,
        estado=execution.estado,
        iniciado_en=execution.iniciado_en,
        completado_en=execution.completado_en,
        duracion_segundos=execution.duracion_segundos,
        metricas=execution.metricas,
        conteo_errores=execution.conteo_errores or 0,
        tasa_error=round(error_rate, 2),
        semaforo=semaphore,
        version_moodle=execution.version_moodle,
        modalidad=execution.modalidad,
    )
