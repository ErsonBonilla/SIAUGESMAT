"""
Tareas Celery para operaciones masivas de creación y eliminación de entidades en Moodle.
"""

import asyncio
import logging

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.operation_repo import (
    complete_batch,
    get_batch,
    get_pending_items,
    update_batch_counts,
    update_item,
)
from app.services.error_messages import translate_error
from app.services.moodle import MoodleAPIError, MoodleService
from app.services.moodle_adapter import resolve_role

logger = logging.getLogger(__name__)


def _get_moodle_service(modalidad: str) -> MoodleService:
    config = settings.get_moodle_config(modalidad)
    return MoodleService(
        token=config["token"],
        base_url=config["url"],
        version=config["version"],
    )


@celery_app.task(bind=True, max_retries=2, default_retry_delay=5)
def process_operation_batch(self, batch_id: str):
    db = SessionLocal()
    try:
        batch = get_batch(db, batch_id)
        if not batch:
            logger.error(f"Lote {batch_id} no encontrado")
            return

        moodle = _get_moodle_service(batch.modalidad)
        items = get_pending_items(db, batch_id)

        try:
            async def _process_all():
                if batch.entity_type == "categories" and batch.action == "create":
                    await _ensure_root_category(moodle)

                for item in items:
                    try:
                        await _process_single_item(item, batch, moodle, db)
                    except MoodleAPIError as e:
                        msg = _format_moodle_error(e, batch.entity_type, item)
                        logger.exception(f"Error en {batch.entity_type} '{item.identifier}': {msg}")
                        update_item(db, item.id, "failed", msg)
                        update_batch_counts(db, batch_id, failed=1)
                    except Exception as exc:
                        logger.exception(
                            f"Error en {batch.entity_type} '{item.identifier}' (lote {batch_id})"
                        )
                        update_item(db, item.id, "failed", translate_error(exc))
                        update_batch_counts(db, batch_id, failed=1)

            asyncio.run(_process_all())
        finally:
            asyncio.run(moodle.close())

        complete_batch(db, batch_id)

    except Exception:
        logger.exception(f"Fallo crítico en lote {batch_id}")
        raise
    finally:
        db.close()


async def _process_single_item(item, batch, moodle, db):
    update_item(db, item.id, "processing")

    if batch.action == "delete":
        if batch.entity_type == "courses":
            result = await moodle.delete_courses([item.identifier])
            if result is None:
                raise ValueError("Curso no encontrado en Moodle. Verifique el shortname.")

        elif batch.entity_type == "categories":
            cats = await moodle.get_categories(idnumber=item.identifier)
            if not cats:
                raise ValueError("Categoría no encontrada en Moodle. Verifique el idnumber.")
            await moodle.delete_category(int(cats[0]["id"]))

        elif batch.entity_type == "users":
            result = await moodle.delete_users([item.identifier])
            if result is None:
                raise ValueError("Usuario no encontrado en Moodle. Verifique el username.")

    elif batch.action == "create":
        if batch.entity_type == "users":
            detail = item.detail or {}
            user_data = {
                "username": item.identifier,
                "firstname": detail.get("firstname", item.identifier),
                "lastname": detail.get("lastname", ""),
                "email": detail.get("email", f"{item.identifier}@ut.edu.co"),
            }
            if detail.get("password"):
                user_data["password"] = detail["password"]
                user_data["forcepasswordchange"] = True
            elif detail.get("forcepasswordchange") == "1":
                user_data["forcepasswordchange"] = True
            else:
                user_data["createpassword"] = True
            created = await moodle.create_users([user_data])

            role = detail.get("role1")
            if role and created and len(created) > 0:
                user_id = created[0].get("id")
                if user_id:
                    role_id = resolve_role(str(role))
                    await moodle.assign_role(int(user_id), role_id)

        elif batch.entity_type == "categories":
            detail = item.detail or {}
            parent_idnumber = detail.get("parent") or "DISTANCIA"
            cat_data = {
                "name": item.identifier,
                "idnumber": detail.get("idnumber") or item.identifier,
                "parent": parent_idnumber,
            }
            if detail.get("description"):
                cat_data["description"] = detail["description"]
            if detail.get("visible") is not None:
                cat_data["visible"] = int(detail["visible"])
            await moodle.create_categories([cat_data])

    update_item(db, item.id, "completed")
    update_batch_counts(db, batch.batch_id, completed=1)


async def _ensure_root_category(moodle: MoodleService):
    try:
        cats = await moodle.get_categories(idnumber="DISTANCIA")
        if not cats:
            await moodle.create_categories([{
                "name": "IDEAD",
                "idnumber": "DISTANCIA",
                "parent": 0,
            }])
            logger.info("Categoría raíz IDEAD (DISTANCIA) creada automáticamente")
    except MoodleAPIError as e:
        logger.error(f"Error al crear categoría raíz IDEAD: {e}")
        raise


def _format_moodle_error(e: MoodleAPIError, entity_type: str, item) -> str:
    code = getattr(e, "error_code", None)
    detail = item.detail or {}

    if code == "duplicateuser":
        return f"El usuario '{item.identifier}' ya existe en Moodle (username duplicado)."
    if code == "invalidemail":
        email = detail.get("email", "")
        return f"Email inválido '{email}' para el usuario '{item.identifier}'."
    if code == "emailnotallowed":
        email = detail.get("email", "")
        return f"El dominio del email '{email}' no está permitido en Moodle para '{item.identifier}'."
    if code == "duplicatecategory":
        return f"La categoría '{item.identifier}' ya existe en Moodle (idnumber duplicado)."
    if code == "cannotfindparentcategory":
        parent = detail.get("parent") or "DISTANCIA"
        return f"Categoría padre '{parent}' no encontrada en Moodle."
    if code == "invalidparameter":
        return f"Parámetro inválido para '{item.identifier}': {e}"
    return e.spanish_message
