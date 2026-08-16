import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.repositories.repositorio_ejecuciones import obtener_ejecucion
from app.repositories.repositorio_registros import obtener_logs_ejecucion
from app.schemas.respuestas import RespuestaListaGraficos
from app.schemas.usuario import UsuarioEnToken
from app.services.graficos import ServicioGraficos

logger = logging.getLogger(__name__)

router = APIRouter()

CHART_ENDPOINTS = {
    "resumen_ejecutivo": ServicioGraficos.resumen_ejecutivo_json,
    "tasa_exito": ServicioGraficos.tasa_exito_json,
    "top_programas": ServicioGraficos.top_programas_json,
    "distribucion_usuarios": ServicioGraficos.distribucion_usuarios_json,
    "top_incidencias": ServicioGraficos.top_incidencias_json,
}

CHART_TITLES = {
    "resumen_ejecutivo": "Resumen ejecutivo",
    "tasa_exito": "Tasa de éxito de matrícula",
    "top_programas": "Top programas",
    "distribucion_usuarios": "Distribución de usuarios",
    "top_incidencias": "Top incidencias",
}


def _obtener_ejecucion_y_registros(ejecucion_id: int, db: Session):
    execution = obtener_ejecucion(db, ejecucion_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    logs = obtener_logs_ejecucion(db, ejecucion_id)
    return execution, logs


@router.get("/executions/{ejecucion_id}/charts", response_model=RespuestaListaGraficos)
async def listar_graficos(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    execution, _logs = _obtener_ejecucion_y_registros(ejecucion_id, db)
    return {
        "execution_id": ejecucion_id,
        "moodle_version": execution.version_moodle,
        "modalidad": execution.modalidad,
        "charts": [
            {
                "id": name,
                "title": CHART_TITLES.get(name, name.replace("_", " ").title()),
                "endpoint": f"/api/v1/analytics/executions/{ejecucion_id}/charts/{name}",
            }
            for name in CHART_ENDPOINTS
        ],
    }


@router.get("/executions/{ejecucion_id}/charts/{nombre_grafico}")
async def obtener_datos_grafico(
    ejecucion_id: int,
    nombre_grafico: str,
    theme: str = Query("light", description="Tema: light | dark"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
) -> dict[str, Any]:
    if nombre_grafico not in CHART_ENDPOINTS:
        raise HTTPException(
            status_code=404,
            detail=f"Gráfico no encontrado. Disponibles: {list(CHART_ENDPOINTS.keys())}",
        )
    execution, logs = _obtener_ejecucion_y_registros(ejecucion_id, db)
    return CHART_ENDPOINTS[nombre_grafico](execution, logs, theme=theme)
