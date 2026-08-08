"""
Endpoints para la descarga de reportes del Módulo de Novedades (FASE 4).

Permite listar, visualizar y descargar los reportes generados durante
una ejecución del proceso ETL.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.repositories.execution_repo import get_execution
from app.schemas.api import ReportsListResponse
from app.schemas.user import UserInToken
from app.services.reports import ReportService

router = APIRouter()


@router.get("/{execution_id}/reports", response_model=ReportsListResponse)
async def list_reports(
    execution_id: int,
    db: Session = Depends(get_db),
    _current_user: UserInToken = Depends(get_current_user),
):
    """Lista los reportes disponibles para una ejecución."""
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    if not execution.report_dir or not os.path.exists(execution.report_dir):
        raise HTTPException(
            status_code=404,
            detail="No hay reportes disponibles para esta ejecución",
        )
    reports = ReportService.list_reports(execution.report_dir)
    return {
        "execution_id": execution_id,
        "report_dir": execution.report_dir,
        "reports": reports,
    }


@router.get("/{execution_id}/reports/{report_name}.csv")
async def download_report(
    execution_id: int,
    report_name: str,
    db: Session = Depends(get_db),
    _current_user: UserInToken = Depends(get_current_user),
):
    """Descarga un reporte CSV específico."""
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    if not execution.report_dir:
        raise HTTPException(status_code=404, detail="No hay reportes disponibles")

    filepath = ReportService.get_report_path(execution.report_dir, report_name)
    if not filepath:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    return FileResponse(
        filepath,
        media_type="text/csv",
        filename=os.path.basename(filepath),
    )


@router.get("/{execution_id}/reports/download")
async def download_all_reports(
    execution_id: int,
    db: Session = Depends(get_db),
    _current_user: UserInToken = Depends(get_current_user),
):
    """Descarga un ZIP con todos los reportes de la ejecución."""
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    if not execution.report_dir:
        raise HTTPException(status_code=404, detail="No hay reportes disponibles")

    zip_path = ReportService.get_zip_path(execution.report_dir)
    if not zip_path:
        raise HTTPException(status_code=404, detail="ZIP de reportes no encontrado")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"reportes_ejecucion_{execution_id}.zip",
    )
