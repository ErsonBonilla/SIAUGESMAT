"""
Endpoints de analítica y semaforización.

Proporciona métricas agregadas por semestre, el estado del semáforo
de la última ejecución y un resumen de la ejecución más reciente.
Los umbrales del semáforo se configuran en las variables de entorno.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.schemas.analitica import (
    EjecucionReciente,
    EstadoSemaforo,
    MetricasSemestre,
)
from app.schemas.usuario import UsuarioEnToken
from app.services.servicio_metricas import (
    obtener_datos_ejecucion_reciente,
    obtener_estado_semaforo,
    obtener_metricas_historial,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/history",
    response_model=list[MetricasSemestre],
    summary="Obtener métricas históricas por semestre",
)
async def obtener_historial(
    limite: int = Query(
        10,
        ge=1,
        le=50,
        alias="limit",
        description="Número máximo de semestres a devolver",
    ),
    modalidad: str | None = Query(
        None,
        description="Filtrar por modalidad (PRESENCIAL, DISTANCIA)",
    ),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    """
    Devuelve una lista con las métricas agregadas de todos los procesos ETL
    ejecutados en cada semestre, ordenados del más reciente al más antiguo.
    Las métricas incluyen totales de cursos creados, usuarios creados,
    matriculaciones, errores y duración promedio.
    """
    try:
        return obtener_metricas_historial(db, limit=limite, modalidad=modalidad)
    except Exception:
        logger.exception("Error al obtener histórico de métricas")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al recuperar el histórico de ejecuciones.",
        ) from None


@router.get(
    "/semaphore",
    response_model=EstadoSemaforo,
    summary="Obtener el estado del semáforo de la última ejecución",
)
async def obtener_semaforo(
    semestre: str | None = Query(
        None,
        alias="semester",
        description="Semestre a evaluar; si se omite se usa el último registrado.",
    ),
    modalidad: str | None = Query(
        None,
        description="Filtrar por modalidad (PRESENCIAL, DISTANCIA)",
    ),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    """
    Devuelve el estado del semáforo (verde, amarillo, rojo) basado en las
    métricas de la última ejecución completada del semestre solicitado
    (o del más reciente si no se especifica).

    Los umbrales se toman de la configuración (ANALYTICS_ERROR_THRESHOLD_*,
    ANALYTICS_MAX_DURATION_*).
    """
    try:
        return obtener_estado_semaforo(db, semester=semestre, modalidad=modalidad)
    except Exception:
        logger.exception("Error al calcular el semáforo")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al calcular el estado del semáforo.",
        ) from None


@router.get(
    "/latest",
    response_model=EjecucionReciente,
    summary="Obtener un resumen de la ejecución más reciente",
)
async def obtener_ejecucion_reciente(
    modalidad: str | None = Query(
        None,
        description="Filtrar por modalidad (PRESENCIAL, DISTANCIA)",
    ),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    """
    Devuelve los detalles de la última ejecución registrada,
    incluyendo métricas, errores y semáforo derivado.
    """
    try:
        return obtener_datos_ejecucion_reciente(db, modalidad=modalidad)
    except ValueError as e:
        # No hay ejecuciones registradas
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception:
        logger.exception("Error al obtener la última ejecución")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al recuperar la última ejecución.",
        ) from None
