"""
Endpoints de gestión de ejecuciones (jobs) del proceso ETL.
"""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.repositories.execution_repo import (
    delete_execution,
    get_execution,
    get_execution_errors,
    list_executions,
    mark_queued,
    pause_execution,
)
from app.schemas.job import (
    ErrorOut,
    ExecutionList,
    ExecutionOut,
    ProcessResponse,
)
from app.schemas.user import UserInToken
from app.workers.tasks import process_etl_file

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{execution_id}/process",
    response_model=ProcessResponse,
    summary="Iniciar el procesamiento ETL de una ejecución",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_process(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No se encontró la ejecución solicitada.")

    if execution.status not in ("pending", "failed", "queued", "review_required", "paused"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La ejecución ya está en estado '{execution.status}'"
                   f" y no puede ser procesada nuevamente.",
        )

    if execution.modalidad == "PRESENCIAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No se puede procesar una ejecución de modalidad PRESENCIAL.",
        )

    file_path = os.path.join(settings.UPLOAD_DIR, execution.filename)
    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo asociado a la ejecución no se encuentra en el servidor.",
        )

    try:
        job = process_etl_file.delay(execution_id, file_path, execution.semester)
    except Exception:
        logger.exception("Error al encolar la tarea ETL")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo encolar la tarea de procesamiento.",
        )

    mark_queued(db, execution_id)

    logger.info(
        f"Tarea encolada para ejecución {execution_id}: task_id={job.id} "
        f"por {current_user.username} (mode={execution.mode})"
    )

    return ProcessResponse(
        execution_id=execution_id,
        job_id=job.id,
        status="queued",
        message="Procesamiento encolado correctamente.",
    )


@router.get(
    "/{execution_id}",
    response_model=ExecutionOut,
    summary="Obtener detalles de una ejecución",
)
async def get_execution_endpoint(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Ejecución no encontrada.")

    # Calcular ETA si está running y tiene datos suficientes
    if execution.status == "running" and execution.progress_pct and execution.progress_updated_at:
        pct = execution.progress_pct
        elapsed = (datetime.now(timezone.utc) - execution.progress_updated_at).total_seconds()
        if elapsed > 10 and pct > 0:
            rate = pct / elapsed
            if rate > 0:
                eta = (100 - pct) / rate
                execution.eta_seconds = eta if eta < 86400 else None

    return execution


@router.get(
    "/{execution_id}/errors",
    response_model=list[ErrorOut],
    summary="Listar errores de una ejecución",
)
async def get_execution_errors_endpoint(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Ejecución no encontrada.")
    return get_execution_errors(db, execution_id, limit, offset)


@router.get(
    "",
    response_model=ExecutionList,
    summary="Listar ejecuciones históricas",
)
async def list_executions_endpoint(
    semester: str | None = Query(None),
    status: str | None = Query(None),
    mode: str | None = Query(None),
    moodle_version: str | None = Query(None),
    modalidad: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    total, executions = list_executions(
        db, semester=semester, status=status, mode=mode,
        moodle_version=moodle_version, modalidad=modalidad,
        limit=limit, offset=offset,
    )
    return ExecutionList(
        total=total,
        items=[ExecutionOut.model_validate(e) for e in executions],
    )


@router.delete(
    "/{execution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una ejecución",
)
async def delete_execution_endpoint(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Ejecución no encontrada.")

    if execution.status not in ("pending", "failed", "review_required"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden eliminar ejecuciones en estado 'pending', 'failed' o 'review_required'.",
        )

    delete_execution(db, execution_id)
    logger.info(f"Ejecución {execution_id} eliminada por {current_user.username}")
    return None


@router.post(
    "/{execution_id}/confirm",
    response_model=ProcessResponse,
    summary="Confirmar eliminación masiva de cursos",
    status_code=status.HTTP_202_ACCEPTED,
)
async def confirm_mass_delete(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Ejecución no encontrada.")

    if execution.status != "review_required":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La ejecución está en estado '{execution.status}'. "
                   f"Solo se puede confirmar ejecuciones en 'review_required'.",
        )

    if execution.modalidad == "PRESENCIAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No se puede procesar una ejecución de modalidad PRESENCIAL.",
        )

    # Marcar como confirmado en el checkpoint
    if execution.phase_checkpoint is None:
        execution.phase_checkpoint = {}
    execution.phase_checkpoint["delete_confirmed"] = True
    flag_modified(execution, "phase_checkpoint")
    execution.status = "pending"
    execution.current_phase = "Eliminación masiva confirmada"
    execution.progress_pct = 30
    db.commit()

    file_path = os.path.join(settings.UPLOAD_DIR, execution.filename)
    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo asociado a la ejecución no se encuentra en el servidor.",
        )

    try:
        job = process_etl_file.delay(execution_id, file_path, execution.semester)
    except Exception:
        logger.exception("Error al encolar la tarea ETL")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo encolar la tarea de procesamiento.",
        )

    mark_queued(db, execution_id)

    logger.info(
        f"Eliminación masiva confirmada para ejecución {execution_id} "
        f"por {current_user.username}"
    )

    return ProcessResponse(
        execution_id=execution_id,
        job_id=job.id,
        status="queued",
        message="Confirmación recibida. Procesamiento reanudado.",
    )


@router.post(
    "/{execution_id}/pause",
    response_model=ProcessResponse,
    summary="Pausar una ejecución en curso",
    status_code=status.HTTP_202_ACCEPTED,
)
async def pause_execution_endpoint(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    execution = get_execution(db, execution_id)
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Ejecución no encontrada.")

    if execution.status != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La ejecución está en estado '{execution.status}'. "
                   f"Solo se puede pausar ejecuciones en 'running'.",
        )

    if not pause_execution(db, execution_id):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="No se pudo pausar la ejecución.")

    logger.info(f"Ejecución {execution_id} pausada por {current_user.username}")
    return ProcessResponse(
        execution_id=execution_id,
        job_id="",
        status="paused",
        message="Ejecución pausada. Usa /process para continuar.",
    )
