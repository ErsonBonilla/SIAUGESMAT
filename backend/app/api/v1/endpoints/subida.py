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
from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.repositories.repositorio_ejecuciones import crear_ejecucion, obtener_ejecucion_activa
from app.repositories.repositorio_operaciones import obtener_lote_activo
from app.schemas.respuestas import RespuestaEstadoSubida
from app.schemas.subida import RespuestaSemestre, RespuestaSubida
from app.schemas.usuario import UsuarioEnToken
from app.services.validacion_excel import es_contenido_excel

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE_MB = 50
ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
ALLOWED_MODES = {"courses", "users", "both"}


@router.get(
    "/current",
    response_model=RespuestaSemestre,
    summary="Obtener el semestre actual según la fecha del servidor",
)
def obtener_semestre_actual():
    from datetime import datetime

    now = datetime.now(UTC)
    period = "A" if now.month <= 6 else "B"
    return RespuestaSemestre(semester=f"{now.year}{period}")


@router.get(
    "/status",
    response_model=RespuestaEstadoSubida,
    summary="Indica si se permite subir archivos para una modalidad",
)
def obtener_estado_subida(
    modalidad: str | None = Query(None),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    mod = (modalidad or usuario_actual.modalidad or "DISTANCIA").strip().upper()
    execution = obtener_ejecucion_activa(db, mod)
    batch = obtener_lote_activo(db, mod)
    return {
        "allowed": not (execution or batch),
        "execution": {
            "id": execution.id,
            "status": execution.estado,
            "filename": execution.nombre_archivo,
        }
        if execution
        else None,
        "batch": {
            "batch_id": batch.id_lote,
            "entity_type": batch.tipo_entidad,
            "action": batch.accion,
        }
        if batch
        else None,
    }


@router.post(
    "",
    response_model=RespuestaSubida,
    summary="Subir archivo Excel",
    status_code=status.HTTP_201_CREATED,
)
async def subir_excel(
    archivo: UploadFile = File(..., alias="file"),
    semestre: str = Form(..., alias="semester"),
    modo: str = Form("both", alias="mode"),
    modalidad: str = Form(...),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    semestre = semestre.strip().upper()
    if len(semestre) != 5 or semestre[-1] not in ("A", "B") or not semestre[:4].isdigit():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"Formato de semestre inválido: '{semestre}'."
        )

    if modo not in ALLOWED_MODES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Modo inválido: '{modo}'.")

    modalidad = modalidad.strip().upper()
    allowed_modalidades = {"DISTANCIA"}
    if settings.ALLOW_PRESENCIAL:
        allowed_modalidades.add("PRESENCIAL")
    if modalidad not in allowed_modalidades:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Modalidad inválida. Solo DISTANCIA está disponible.",
        )

    if obtener_ejecucion_activa(db, modalidad) or obtener_lote_activo(db, modalidad):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Hay un proceso en curso en esta modalidad. "
            "No se pueden subir archivos hasta que el proceso en ejecución finalice.",
        )

    if not archivo.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="El archivo debe tener un nombre.")

    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Extensión no permitida: '{ext}'.")

    file_bytes = await archivo.read()
    file_size_mb = len(file_bytes) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo excede {MAX_FILE_SIZE_MB} MB.",
        )

    if not es_contenido_excel(file_bytes):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                "El archivo no es un Excel válido. Verifique que sea un "
                "archivo .xlsx o .xls real, que no esté dañado y vuelva a "
                "intentarlo."
            ),
        )

    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)

    safe_filename = os.path.basename(archivo.filename)
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_filename}"
    file_path = os.path.join(upload_dir, unique_name)

    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except OSError:
        logger.exception("Error al guardar el archivo")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo guardar el archivo."
        ) from None

    moodle_config = settings.obtener_config_moodle(modalidad)
    execution = crear_ejecucion(
        db, unique_name, semestre, modo, modalidad, moodle_config["version"]
    )

    logger.info(
        f"Archivo '{unique_name}' subido por {usuario_actual.username} "
        f"(execution_id={execution.id}, mode={modo})"
    )

    return RespuestaSubida(
        execution_id=execution.id,
        filename=unique_name,
        semester=semestre,
        mode=modo,
        status=execution.estado,
        message="Archivo subido correctamente. Pendiente de procesamiento.",
    )
