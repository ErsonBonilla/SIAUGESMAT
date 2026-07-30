import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.repositories.operation_repo import (
    delete_batch,
    delete_old_batches,
    get_all_batch_items,
    get_batch,
    get_batch_items,
    get_batch_status,
    pause_batch,
    resume_batch,
)
from app.schemas.operations import BatchStatusResponse, DeleteOldBatchesResponse, OperationItemOut
from app.schemas.user import UserInToken
from app.services.batch_report_service import build_batch_report_zip

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/batch/{batch_id}/status", response_model=BatchStatusResponse,
            summary="Consultar estado de un lote de operaciones")
def get_batch_status_endpoint(
    batch_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db), current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    st = get_batch_status(db, batch_id)
    items = get_batch_items(db, batch_id, offset, limit)

    return BatchStatusResponse(
        batch_id=batch.batch_id, entity_type=batch.entity_type, action=batch.action,
        total=st["total"], pending=st["pending"], processing=st["processing"],
        paused=st["paused"], completed=st["completed"], failed=st["failed"],
        offset=offset, limit=limit,
        details=[OperationItemOut(
            identifier=i.identifier, status=i.status,
            error_message=i.error_message, attempt=i.attempt,
        ) for i in items],
    )


@router.post("/batch/{batch_id}/pause",
             summary="Pausar un lote de operaciones")
def pause_batch_endpoint(
    batch_id: str,
    db: Session = Depends(get_db), current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    paused = pause_batch(db, batch_id)
    logger.info(f"Lote {batch_id} pausado por {current_user.username}: {paused} items")
    return {"batch_id": batch_id, "paused": paused, "message": f"Lote pausado. {paused} items pendientes marcados como pausados."}


@router.post("/batch/{batch_id}/resume",
             summary="Reanudar un lote de operaciones pausado")
def resume_batch_endpoint(
    batch_id: str,
    db: Session = Depends(get_db), current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    resumed = resume_batch(db, batch_id)
    logger.info(f"Lote {batch_id} reanudado por {current_user.username}: {resumed} items")
    return {"batch_id": batch_id, "resumed": resumed, "message": f"Lote reanudado. {resumed} items vueltos a pendientes."}


@router.delete("/batch/{batch_id}",
               summary="Eliminar un lote de operaciones")
def delete_batch_endpoint(
    batch_id: str,
    db: Session = Depends(get_db), current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if not delete_batch(db, batch_id):
        raise HTTPException(status_code=500, detail="No se pudo eliminar el lote")
    logger.info(f"Lote {batch_id} eliminado por {current_user.username}")
    return {"batch_id": batch_id, "message": "Lote eliminado correctamente."}


@router.get("/batch/{batch_id}/reports/download",
            summary="Descargar reportes (ZIP con CSVs)")
def download_batch_reports(
    batch_id: str, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    items = get_all_batch_items(db, batch_id)
    zip_path, zip_filename = build_batch_report_zip(batch, items)
    background_tasks.add_task(os.unlink, zip_path)
    return FileResponse(path=zip_path, media_type="application/zip", filename=zip_filename)


@router.delete("/batches/old", response_model=DeleteOldBatchesResponse,
               summary="Eliminar lotes antiguos")
def delete_old(
    days: int = Query(30, ge=1), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    deleted = delete_old_batches(db, days)
    return DeleteOldBatchesResponse(deleted_batches=deleted, older_than_days=days)
