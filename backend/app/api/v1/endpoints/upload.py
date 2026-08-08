"""
Endpoints de subida de archivos Excel (carga académica).
"""

import logging
import os
import uuid
from datetime import UTC

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.repositories.execution_repo import create_execution, get_active_execution
from app.repositories.operation_repo import get_active_batch
from app.schemas.upload import SemesterResponse, UploadResponse
from app.schemas.user import UserInToken

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE_MB = 50
ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
ALLOWED_MODES = {"courses", "users", "both"}


@router.get("/current", response_model=SemesterResponse,
            summary="Obtener el semestre actual según la fecha del servidor")
def get_current_semester():
    from datetime import datetime
    now = datetime.now(UTC)
    period = "A" if now.month <= 6 else "B"
    return SemesterResponse(semester=f"{now.year}{period}")


@router.get("/status",
            summary="Indica si se permite subir archivos para una modalidad")
def get_upload_status(
    modalidad: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    mod = (modalidad or current_user.modalidad or "DISTANCIA").strip().upper()
    execution = get_active_execution(db, mod)
    batch = get_active_batch(db, mod)
    return {
        "allowed": not (execution or batch),
        "execution": {
            "id": execution.id,
            "status": execution.status,
            "filename": execution.filename,
        } if execution else None,
        "batch": {
            "batch_id": batch.batch_id,
            "entity_type": batch.entity_type,
            "action": batch.action,
        } if batch else None,
    }


@router.post("", response_model=UploadResponse, summary="Subir archivo Excel",
             status_code=status.HTTP_201_CREATED)
async def upload_excel(
    file: UploadFile = File(...),
    semester: str = Form(...),
    mode: str = Form("both"),
    modalidad: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    semester = semester.strip().upper()
    if len(semester) != 5 or semester[-1] not in ("A", "B") or not semester[:4].isdigit():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail=f"Formato de semestre inválido: '{semester}'.")

    if mode not in ALLOWED_MODES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail=f"Modo inválido: '{mode}'.")

    modalidad = modalidad.strip().upper()
    allowed_modalidades = {"DISTANCIA"}
    if settings.ALLOW_PRESENCIAL:
        allowed_modalidades.add("PRESENCIAL")
    if modalidad not in allowed_modalidades:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="Modalidad inválida. Solo DISTANCIA está disponible.")

    if get_active_execution(db, modalidad) or get_active_batch(db, modalidad):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Hay un proceso en curso en esta modalidad. "
                   "No se pueden subir archivos hasta que el proceso en ejecución finalice.",
        )

    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="El archivo debe tener un nombre.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail=f"Extensión no permitida: '{ext}'.")

    file_bytes = await file.read()
    file_size_mb = len(file_bytes) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"El archivo excede {MAX_FILE_SIZE_MB} MB.")

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)

    safe_filename = os.path.basename(file.filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_filename}"
    file_path = os.path.join(upload_dir, unique_name)

    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except OSError:
        logger.exception("Error al guardar el archivo")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="No se pudo guardar el archivo.") from None

    moodle_config = settings.get_moodle_config(modalidad)
    execution = create_execution(db, unique_name, semester, mode,
                                 modalidad, moodle_config["version"])

    logger.info(f"Archivo '{unique_name}' subido por {current_user.username} "
                f"(execution_id={execution.id}, mode={mode})")

    return UploadResponse(
        execution_id=execution.id, filename=unique_name,
        semester=semester, mode=mode, status=execution.status,
        message="Archivo subido correctamente. Pendiente de procesamiento.",
    )
