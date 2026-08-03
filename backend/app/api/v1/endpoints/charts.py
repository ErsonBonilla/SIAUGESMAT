import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.repositories.execution_repo import get_execution
from app.repositories.log_repo import get_execution_logs
from app.schemas.user import UserInToken
from app.services.charts import ChartService

logger = logging.getLogger(__name__)

router = APIRouter()

CHART_ENDPOINTS = {
    "resumen_ejecutivo": ChartService.resumen_ejecutivo_json,
    "tasa_exito": ChartService.tasa_exito_json,
    "top_programas": ChartService.top_programas_json,
    "distribucion_usuarios": ChartService.distribucion_usuarios_json,
    "top_incidencias": ChartService.top_incidencias_json,
}

CHART_TITLES = {
    "resumen_ejecutivo": "Resumen ejecutivo",
    "tasa_exito": "Tasa de éxito de matrícula",
    "top_programas": "Top programas",
    "distribucion_usuarios": "Distribución de usuarios",
    "top_incidencias": "Top incidencias",
}


def _get_execution_and_logs(execution_id: int, db: Session):
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    logs = get_execution_logs(db, execution_id)
    return execution, logs


@router.get("/executions/{execution_id}/charts")
async def list_charts(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    execution, _logs = _get_execution_and_logs(execution_id, db)
    return {
        "execution_id": execution_id,
        "moodle_version": execution.moodle_version,
        "modalidad": execution.modalidad,
        "charts": [
            {
                "id": name,
                "title": CHART_TITLES.get(name, name.replace("_", " ").title()),
                "endpoint": f"/api/v1/analytics/executions/{execution_id}/charts/{name}",
            }
            for name in CHART_ENDPOINTS
        ],
    }


@router.get("/executions/{execution_id}/charts/{chart_name}")
async def get_chart_data(
    execution_id: int,
    chart_name: str,
    theme: str = Query("light", description="Tema: light | dark"),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
) -> dict[str, Any]:
    if chart_name not in CHART_ENDPOINTS:
        raise HTTPException(
            status_code=404,
            detail=f"Gráfico no encontrado. Disponibles: {list(CHART_ENDPOINTS.keys())}",
        )
    execution, logs = _get_execution_and_logs(execution_id, db)
    return CHART_ENDPOINTS[chart_name](execution, logs, theme=theme)
