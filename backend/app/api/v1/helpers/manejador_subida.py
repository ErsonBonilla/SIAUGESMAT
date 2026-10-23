import logging
import uuid

from fastapi import HTTPException, UploadFile

from app.core.configuracion_entidades import CONFIG_ENTIDADES
from app.repositories.repositorio_ejecuciones import obtener_ejecucion_activa
from app.repositories.repositorio_operaciones import agregar_item, crear_lote, obtener_lote_activo
from app.schemas.operaciones import RespuestaSubidaCsv
from app.services.orquestacion import encolar_lote_operacion
from app.services.validador_csv import (
    validar_csv_categorias,
    validar_csv_usuarios,
    validar_y_parsear_csv,
)

logger = logging.getLogger(__name__)


def _ensure_modalidad_free(db, modalidad: str) -> None:
    """Rechaza la subida si hay un proceso en curso para la modalidad."""
    if obtener_ejecucion_activa(db, modalidad) or obtener_lote_activo(db, modalidad):
        raise HTTPException(
            409,
            "Hay un proceso en ejecución en esta modalidad. "
            "No se pueden subir archivos hasta que el proceso en curso finalice.",
        )


async def manejar_subida_visibilidad(file: UploadFile, db, current_user, visibility: str):
    config = CONFIG_ENTIDADES["courses"]
    _ensure_modalidad_free(db, current_user.modalidad)

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se aceptan archivos CSV")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "El archivo no es un texto UTF-8 válido") from None

    try:
        identifiers = validar_y_parsear_csv(text, config["column"], config["label_plural"])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    batch_id = str(uuid.uuid4())
    crear_lote(db, batch_id, "courses", "visibility", len(identifiers), current_user.modalidad)

    for identifier in identifiers:
        agregar_item(db, batch_id, identifier, detalle={"visibility": visibility})
    db.commit()

    encolar_lote_operacion(batch_id)

    verb_label = "mostrar" if visibility == "show" else "ocultar"
    logger.info(
        f"Lote {batch_id} (cambiar visibilidad a {visibility} de {len(identifiers)} cursos) "
        f"encolado por {current_user.username}"
    )

    return RespuestaSubidaCsv(
        batch_id=batch_id,
        entity_type="courses",
        action="visibility",
        total=len(identifiers),
        message=f"Se encolaron {len(identifiers)} cursos para {verb_label}.",
    )


async def manejar_subida(
    file: UploadFile, db, current_user, entity_type, action, default_role=None
):
    config = CONFIG_ENTIDADES[entity_type]
    _ensure_modalidad_free(db, current_user.modalidad)

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se aceptan archivos CSV")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "El archivo no es un texto UTF-8 válido") from None

    try:
        is_create_users = entity_type == "users" and action == "create"
        is_create_categories = entity_type == "categories" and action == "create"
        if is_create_users:
            users = validar_csv_usuarios(text, default_role=default_role)
            identifiers = [u["username"] for u in users]
        elif is_create_categories:
            categories = validar_csv_categorias(text)
            identifiers = [c["name"] for c in categories]
        else:
            identifiers = validar_y_parsear_csv(text, config["column"], config["label_plural"])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    batch_id = str(uuid.uuid4())
    crear_lote(db, batch_id, entity_type, action, len(identifiers), current_user.modalidad)

    if is_create_users:
        for user in users:
            agregar_item(
                db,
                batch_id,
                user["username"],
                detalle={
                    "firstname": user["firstname"],
                    "lastname": user["lastname"],
                    "email": user["email"],
                    "role1": user.get("role1"),
                    "forcepasswordchange": user.get("forcepasswordchange"),
                },
            )
    elif is_create_categories:
        for cat in categories:
            agregar_item(
                db,
                batch_id,
                cat["name"],
                detalle={
                    "idnumber": cat.get("idnumber"),
                    "parent": cat.get("parent"),
                    "description": cat.get("description"),
                    "visible": cat.get("visible"),
                },
            )
    else:
        for identifier in identifiers:
            agregar_item(db, batch_id, identifier)
    db.commit()

    encolar_lote_operacion(batch_id)

    verb = "eliminación" if action == "delete" else "creación"
    logger.info(
        f"Lote {batch_id} ({verb} de {len(identifiers)} {config['label_plural']}) "
        f"encolado por {current_user.username}"
    )

    return RespuestaSubidaCsv(
        batch_id=batch_id,
        entity_type=entity_type,
        action=action,
        total=len(identifiers),
        message=f"Se encolaron {len(identifiers)} {config['label_plural']} para {verb}.",
    )
