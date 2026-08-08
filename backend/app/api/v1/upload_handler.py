import logging
import uuid

from fastapi import HTTPException, UploadFile

from app.core.entity_config import ENTITY_CONFIG
from app.repositories.execution_repo import get_active_execution
from app.repositories.operation_repo import add_item, create_batch, get_active_batch
from app.schemas.operations import CsvUploadResponse
from app.services.csv_validator import (
    validate_and_parse_csv,
    validate_categories_csv,
    validate_users_csv,
)
from app.workers.operations_tasks import process_operation_batch

logger = logging.getLogger(__name__)


def _ensure_modalidad_free(db, modalidad: str) -> None:
    """Rechaza la subida si hay un proceso en curso para la modalidad."""
    if get_active_execution(db, modalidad) or get_active_batch(db, modalidad):
        raise HTTPException(
            409,
            "Hay un proceso en ejecución en esta modalidad. "
            "No se pueden subir archivos hasta que el proceso en curso finalice.",
        )


async def handle_visibility_upload(file: UploadFile, db, current_user, visibility: str):
    config = ENTITY_CONFIG["courses"]
    _ensure_modalidad_free(db, current_user.modalidad)

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se aceptan archivos CSV")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "El archivo no es un texto UTF-8 válido") from None

    try:
        identifiers = validate_and_parse_csv(text, config["column"], config["label_plural"])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    batch_id = str(uuid.uuid4())
    create_batch(db, batch_id, "courses", "visibility", len(identifiers), current_user.modalidad)

    for identifier in identifiers:
        add_item(db, batch_id, identifier, detail={"visibility": visibility})
    db.commit()

    process_operation_batch.delay(batch_id)

    verb_label = "mostrar" if visibility == "show" else "ocultar"
    logger.info(f"Lote {batch_id} (cambiar visibilidad a {visibility} de {len(identifiers)} cursos) "
                f"encolado por {current_user.username}")

    return CsvUploadResponse(
        batch_id=batch_id, entity_type="courses", action="visibility",
        total=len(identifiers),
        message=f"Se encolaron {len(identifiers)} cursos para {verb_label}.",
    )


async def handle_upload(file: UploadFile, db, current_user, entity_type, action, default_role=None):
    config = ENTITY_CONFIG[entity_type]
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
            users = validate_users_csv(text, default_role=default_role)
            identifiers = [u["username"] for u in users]
        elif is_create_categories:
            categories = validate_categories_csv(text)
            identifiers = [c["name"] for c in categories]
        else:
            identifiers = validate_and_parse_csv(text, config["column"], config["label_plural"])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    batch_id = str(uuid.uuid4())
    create_batch(db, batch_id, entity_type, action, len(identifiers), current_user.modalidad)

    if is_create_users:
        for user in users:
            add_item(db, batch_id, user["username"], detail={
                "firstname": user["firstname"], "lastname": user["lastname"],
                "email": user["email"], "password": user.get("password"),
                "role1": user.get("role1"),
                "forcepasswordchange": user.get("forcepasswordchange"),
            })
    elif is_create_categories:
        for cat in categories:
            add_item(db, batch_id, cat["name"], detail={
                "idnumber": cat.get("idnumber"), "parent": cat.get("parent"),
                "description": cat.get("description"), "visible": cat.get("visible"),
            })
    else:
        for identifier in identifiers:
            add_item(db, batch_id, identifier)
    db.commit()

    process_operation_batch.delay(batch_id)

    verb = "eliminación" if action == "delete" else "creación"
    logger.info(f"Lote {batch_id} ({verb} de {len(identifiers)} {config['label_plural']}) "
                f"encolado por {current_user.username}")

    return CsvUploadResponse(
        batch_id=batch_id, entity_type=entity_type, action=action,
        total=len(identifiers),
        message=f"Se encolaron {len(identifiers)} {config['label_plural']} para {verb}.",
    )
