"""
Endpoints para la descarga de reportes del Módulo de Novedades (FASE 4).

Permite listar, visualizar y descargar los reportes generados durante
una ejecución del proceso ETL.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.repositories.repositorio_ejecuciones import obtener_ejecucion
from app.schemas.respuestas import RespuestaListaReportes
from app.schemas.usuario import UsuarioEnToken
from app.services.reportes import ServicioReportes

router = APIRouter()


@router.get("/{ejecucion_id}/reports", response_model=RespuestaListaReportes)
async def listar_reportes(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    _usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    """Lista los reportes disponibles para una ejecución."""
    execution = obtener_ejecucion(db, ejecucion_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    if not execution.directorio_reporte or not os.path.exists(execution.directorio_reporte):
        raise HTTPException(
            status_code=404,
            detail="No hay reportes disponibles para esta ejecución",
        )
    reports = ServicioReportes.listar_reportes(execution.directorio_reporte)
    return {
        "execution_id": ejecucion_id,
        "report_dir": execution.directorio_reporte,
        "reports": reports,
    }


@router.get("/{ejecucion_id}/reports/{nombre_reporte}.csv")
async def descargar_reporte(
    ejecucion_id: int,
    nombre_reporte: str,
    db: Session = Depends(obtener_db),
    _usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    """Descarga un reporte CSV específico."""
    execution = obtener_ejecucion(db, ejecucion_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    if not execution.directorio_reporte:
        raise HTTPException(status_code=404, detail="No hay reportes disponibles")

    filepath = ServicioReportes.obtener_ruta_reporte(execution.directorio_reporte, nombre_reporte)
    if not filepath:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    return FileResponse(
        filepath,
        media_type="text/csv",
        filename=os.path.basename(filepath),
    )


@router.get("/{ejecucion_id}/reports/download")
async def descargar_todos_los_reportes(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    _usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    """Descarga un ZIP con todos los reportes de la ejecución."""
    execution = obtener_ejecucion(db, ejecucion_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    if not execution.directorio_reporte:
        raise HTTPException(status_code=404, detail="No hay reportes disponibles")

    zip_path = ServicioReportes.obtener_ruta_zip(execution.directorio_reporte)
    if not zip_path:
        raise HTTPException(status_code=404, detail="ZIP de reportes no encontrado")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"reportes_ejecucion_{ejecucion_id}.zip",
    )
