import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.repositories.operation_repo import (
    cancel_batch,
    delete_batch,
    get_all_batch_items,
    get_batch,
    get_batch_items,
    get_batch_status,
    pause_batch,
    resume_batch,
)
from app.schemas.api import (
    BatchActionResponse,
    BatchCancelResponse,
    BatchPauseResponse,
    BatchReportsListResponse,
    BatchResumeResponse,
)
from app.schemas.operations import BatchStatusResponse, OperationItemOut
from app.schemas.user import UserInToken
from app.services.batch_report_service import (
    build_batch_report_zip,
    get_batch_report_path,
    list_batch_reports,
    save_batch_reports,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/batch/{batch_id}/status",
    response_model=BatchStatusResponse,
    summary="Consultar estado de un lote de operaciones",
)
def get_batch_status_endpoint(
    batch_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    st = get_batch_status(db, batch_id)
    items = get_batch_items(db, batch_id, offset, limit)

    return BatchStatusResponse(
        batch_id=batch.batch_id,
        entity_type=batch.entity_type,
        action=batch.action,
        total=st["total"],
        pending=st["pending"],
        processing=st["processing"],
        paused=st["paused"],
        completed=st["completed"],
        failed=st["failed"],
        cancelled=st["cancelled"],
        modalidad=batch.modalidad,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
        offset=offset,
        limit=limit,
        details=[
            OperationItemOut(
                identifier=i.identifier,
                status=i.status,
                error_message=i.error_message,
                attempt=i.attempt,
            )
            for i in items
        ],
    )


@router.post(
    "/batch/{batch_id}/pause",
    response_model=BatchPauseResponse,
    summary="Pausar un lote de operaciones",
)
def pause_batch_endpoint(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    paused = pause_batch(db, batch_id)
    logger.info(f"Lote {batch_id} pausado por {current_user.username}: {paused} items")
    return {
        "batch_id": batch_id,
        "paused": paused,
        "message": f"Lote pausado. {paused} items pendientes marcados como pausados.",
    }


@router.post(
    "/batch/{batch_id}/resume",
    response_model=BatchResumeResponse,
    summary="Reanudar un lote de operaciones pausado",
)
def resume_batch_endpoint(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    resumed = resume_batch(db, batch_id)
    logger.info(f"Lote {batch_id} reanudado por {current_user.username}: {resumed} items")
    return {
        "batch_id": batch_id,
        "resumed": resumed,
        "message": f"Lote reanudado. {resumed} items vueltos a pendientes.",
    }


@router.post(
    "/batch/{batch_id}/cancel",
    response_model=BatchCancelResponse,
    summary="Cancelar un lote de operaciones",
)
def cancel_batch_endpoint(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    cancelled = cancel_batch(db, batch_id)
    logger.info(f"Lote {batch_id} cancelado por {current_user.username}: {cancelled} items")
    return {
        "batch_id": batch_id,
        "cancelled": cancelled,
        "message": f"Lote cancelado. {cancelled} items marcados como cancelados.",
    }


@router.delete(
    "/batch/{batch_id}",
    response_model=BatchActionResponse,
    summary="Eliminar un lote de operaciones",
)
def delete_batch_endpoint(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if not delete_batch(db, batch_id):
        raise HTTPException(status_code=500, detail="No se pudo eliminar el lote")
    logger.info(f"Lote {batch_id} eliminado por {current_user.username}")
    return {"batch_id": batch_id, "message": "Lote eliminado correctamente."}


@router.get(
    "/batch/{batch_id}/reports",
    response_model=BatchReportsListResponse,
    summary="Listar reportes individuales de un lote",
)
def list_batch_reports_endpoint(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    return {"batch_id": batch_id, "reports": list_batch_reports(batch_id)}


@router.get("/batch/{batch_id}/reports/download", summary="Descargar reportes (ZIP con CSVs)")
def download_batch_reports(
    batch_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    items = get_all_batch_items(db, batch_id)
    save_batch_reports(batch, items)
    zip_path = os.path.join(os.path.join(settings.REPORT_DIR, "batch", batch_id) + ".zip")
    if not os.path.exists(zip_path):
        zip_path, zip_filename = build_batch_report_zip(batch, items)
        background_tasks.add_task(os.unlink, zip_path)
        return FileResponse(path=zip_path, media_type="application/zip", filename=zip_filename)
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"reportes_{batch.action}_{batch.entity_type}_{batch_id[:8]}.zip",
    )


@router.get(
    "/batch/{batch_id}/reports/{report_name}", summary="Descargar un CSV individual de un lote"
)
def download_batch_report(
    batch_id: str,
    report_name: str,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    path = get_batch_report_path(batch_id, report_name)
    if not path:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return FileResponse(path=path, media_type="text/csv", filename=f"{report_name}.csv")
