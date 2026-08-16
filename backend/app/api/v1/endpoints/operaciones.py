import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.helpers.manejador_subida import manejar_subida, manejar_subida_visibilidad
from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.schemas.operaciones import RespuestaSubidaCsv
from app.schemas.usuario import UsuarioEnToken

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/courses/upload-csv", response_model=RespuestaSubidaCsv, summary="Eliminar cursos masivamente"
)
async def eliminar_cursos_csv(
    archivo: UploadFile = File(..., alias="file"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return await manejar_subida(archivo, db, usuario_actual, entity_type="courses", action="delete")


@router.post(
    "/categories/upload-csv",
    response_model=RespuestaSubidaCsv,
    summary="Eliminar categorías masivamente",
)
async def eliminar_categorias_csv(
    archivo: UploadFile = File(..., alias="file"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return await manejar_subida(
        archivo, db, usuario_actual, entity_type="categories", action="delete"
    )


@router.post(
    "/users/upload-csv", response_model=RespuestaSubidaCsv, summary="Eliminar usuarios masivamente"
)
async def eliminar_usuarios_csv(
    archivo: UploadFile = File(..., alias="file"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return await manejar_subida(archivo, db, usuario_actual, entity_type="users", action="delete")


@router.post(
    "/courses/visibility",
    response_model=RespuestaSubidaCsv,
    summary="Cambiar visibilidad de cursos masivamente",
)
async def visibilidad_masiva_cursos(
    archivo: UploadFile = File(..., alias="file"),
    visibilidad: str = Query("show", alias="visibility", regex="^(show|hide)$"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return await manejar_subida_visibilidad(archivo, db, usuario_actual, visibilidad)


@router.post(
    "/users/create-csv", response_model=RespuestaSubidaCsv, summary="Crear usuarios masivamente"
)
async def crear_usuarios_csv(
    archivo: UploadFile = File(..., alias="file"),
    rol_por_defecto: str | None = Query(None, alias="default_role"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return await manejar_subida(
        archivo,
        db,
        usuario_actual,
        entity_type="users",
        action="create",
        default_role=rol_por_defecto,
    )


@router.post(
    "/categories/create-csv",
    response_model=RespuestaSubidaCsv,
    summary="Crear categorías masivamente",
)
async def crear_categorias_csv(
    archivo: UploadFile = File(..., alias="file"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return await manejar_subida(
        archivo, db, usuario_actual, entity_type="categories", action="create"
    )
