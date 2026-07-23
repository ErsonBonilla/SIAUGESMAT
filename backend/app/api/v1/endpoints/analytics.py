"""
Endpoints de analítica y semaforización.

Proporciona métricas agregadas por semestre, el estado del semáforo
de la última ejecución y un resumen de la ejecución más reciente.
Los umbrales del semáforo se configuran en las variables de entorno.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analytics.metrics import (
    get_history_metrics,
    get_latest_execution_data,
    get_semaphore_status,
)
from app.core.dependencies import get_current_user, get_db
from app.schemas.analytics import (
    LatestExecution,
    SemesterMetrics,
    SemaphoreStatus,
)
from app.schemas.user import UserInToken

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/history",
    response_model=List[SemesterMetrics],
    summary="Obtener métricas históricas por semestre",
)
async def get_history(
    limit: int = Query(
        10,
        ge=1,
        le=50,
        description="Número máximo de semestres a devolver",
    ),
    modalidad: Optional[str] = Query(
        None,
        description="Filtrar por modalidad (PRESENCIAL, DISTANCIA)",
    ),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    """
    Devuelve una lista con las métricas agregadas de todos los procesos ETL
    ejecutados en cada semestre, ordenados del más reciente al más antiguo.
    Las métricas incluyen totales de cursos creados, usuarios creados,
    matriculaciones, errores y duración promedio.
    """
    try:
        return get_history_metrics(db, limit=limit, modalidad=modalidad)
    except Exception as e:
        logger.exception("Error al obtener histórico de métricas")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al recuperar el histórico de ejecuciones.",
        )


@router.get(
    "/semaphore",
    response_model=SemaphoreStatus,
    summary="Obtener el estado del semáforo de la última ejecución",
)
async def get_semaphore(
    semester: Optional[str] = Query(
        None,
        description="Semestre a evaluar; si se omite se usa el último registrado.",
    ),
    modalidad: Optional[str] = Query(
        None,
        description="Filtrar por modalidad (PRESENCIAL, DISTANCIA)",
    ),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    """
    Devuelve el estado del semáforo (verde, amarillo, rojo) basado en las
    métricas de la última ejecución completada del semestre solicitado
    (o del más reciente si no se especifica).

    Los umbrales se toman de la configuración (ANALYTICS_ERROR_THRESHOLD_*,
    ANALYTICS_MAX_DURATION_*).
    """
    try:
        return get_semaphore_status(db, semester=semester, modalidad=modalidad)
    except Exception as e:
        logger.exception("Error al calcular el semáforo")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al calcular el estado del semáforo.",
        )


@router.get(
    "/latest",
    response_model=LatestExecution,
    summary="Obtener un resumen de la ejecución más reciente",
)
async def get_latest_execution(
    modalidad: Optional[str] = Query(
        None,
        description="Filtrar por modalidad (PRESENCIAL, DISTANCIA)",
    ),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    """
    Devuelve los detalles de la última ejecución registrada,
    incluyendo métricas, errores y semáforo derivado.
    """
    try:
        return get_latest_execution_data(db, modalidad=modalidad)
    except ValueError as e:
        # No hay ejecuciones registradas
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Error al obtener la última ejecución")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al recuperar la última ejecución.",
        )