import logging
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.schemas.novedades import ItemNovedad, RespuestaNovedades
from app.schemas.usuario import UsuarioEnToken
from app.services.servicio_novedades import detectar as detectar_novedades
from app.services.validacion_excel import es_contenido_excel

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE_MB = 50
ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


@router.post(
    "/compare",
    response_model=RespuestaNovedades,
    summary="Comparar nueva carga académica con la anterior del mismo semestre",
)
async def comparar_novedades(
    archivo: UploadFile = File(..., alias="file"),
    semestre: str = Form(..., alias="semester"),
    modalidad: str = Form("DISTANCIA"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    semestre = semestre.strip().upper()
    if len(semestre) != 5 or semestre[-1] not in ("A", "B") or not semestre[:4].isdigit():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"Formato de semestre inválido: '{semestre}'."
        )

    modalidad = modalidad.strip().upper()
    allowed_modalidades = {"DISTANCIA"}
    if settings.ALLOW_PRESENCIAL:
        allowed_modalidades.add("PRESENCIAL")
    if modalidad not in allowed_modalidades:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Modalidad inválida.")

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
    unique_name = f"{uuid.uuid4().hex[:8]}_novedades_{safe_filename}"
    file_path = os.path.join(upload_dir, unique_name)

    try:
        with open(file_path, "wb") as f:
            f.write(file_bytes)
    except OSError:
        logger.exception("Error al guardar el archivo")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo guardar el archivo."
        ) from None

    result, error = await detectar_novedades(db, semestre, modalidad, file_path)
    if error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=error)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No se pudieron detectar novedades.")

    novedades_items = [ItemNovedad(**n) for n in result["novedades"]]

    return RespuestaNovedades(
        semester=result["semester"],
        previous_execution_id=result["previous_execution_id"],
        previous_filename=result["previous_filename"],
        total_compared=result["total_compared"],
        novedades=novedades_items,
    )
