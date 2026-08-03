"""
Tareas Celery para operaciones masivas de creación y eliminación de entidades en Moodle.
"""

import logging

from app.celery_app import celery_app
from app.core.config import settings
from app.db.models import OperationItem
from app.db.session import SessionLocal
from app.repositories.operation_repo import (
    complete_batch,
    get_batch,
    get_pending_items,
    update_batch_counts,
    update_item,
)
from app.services.error_messages import translate_error
from app.services.moodle_errors import MoodleAPIError
from app.services.moodle_factory import get_moodle_service
from app.services.moodle_operations import MoodleService
from app.services.roles import resolve_role
from app.workers.utils import run_moodle_async

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=5)
def process_operation_batch(self, batch_id: str):
    db = SessionLocal()
    try:
        batch = get_batch(db, batch_id)
        if not batch:
            logger.error(f"Lote {batch_id} no encontrado")
            return

        moodle = get_moodle_service(batch.modalidad)
        items = get_pending_items(db, batch_id)

        async def _process_all():
            if batch.entity_type == "categories" and batch.action == "create":
                await _ensure_root_category(moodle)

            for item in items:
                # Re-consultar batch por si fue pausado o cancelado
                try:
                    paused = db.query(OperationItem).filter_by(
                        batch_id=batch_id, status="paused"
                    ).count()
                    cancelled = db.query(OperationItem).filter_by(
                        batch_id=batch_id, status="cancelled"
                    ).count()
                    if paused > 0:
                        logger.info(f"Lote {batch_id} pausado, deteniendo procesamiento ({paused} items)")
                        break
                    if cancelled > 0:
                        logger.info(f"Lote {batch_id} cancelado, deteniendo procesamiento ({cancelled} items)")
                        break
                except TypeError:
                    pass
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

        run_moodle_async(moodle, _process_all())

        complete_batch(db, batch_id)

    except Exception:
        logger.exception(f"Fallo crítico en lote {batch_id}")
        raise
    finally:
        db.close()


_DELETE_NOT_FOUND_MESSAGE = {
    "users": "Usuario no encontrado en Moodle. Se omite (ya no existía).",
    "courses": "Curso no encontrado en Moodle. Se omite (ya no existía).",
    "categories": "Categoría no encontrada en Moodle. Se omite (ya no existía).",
}


async def _entity_exists(moodle, entity_type: str, identifier: str) -> bool:
    if entity_type == "users":
        return await moodle.get_user_by_username(identifier) is not None
    if entity_type == "courses":
        return bool(await moodle.get_courses(shortname=identifier))
    if entity_type == "categories":
        return bool(await moodle.get_categories(idnumber=identifier))
    return True


async def _delete_entity(moodle, entity_type: str, identifier: str) -> str:
    """Elimina la entidad en Moodle de forma idempotente.

    Devuelve ``"deleted"`` si el borrado se concretó (o ya no existía tras un
    error transitorio) y ``"not_found"`` si la entidad no existía al inicio.

    Si la llamada a Moodle lanza una excepción, verifica si la entidad sigue
    existiendo: si ya no existe, el borrado sí se concretó (p. ej. timeout con
    respuesta perdida) y se trata como éxito; solo se re-lanza la excepción
    cuando la entidad sigue presente (fallo real).
    """
    try:
        if entity_type == "users":
            result = await moodle.delete_users([identifier])
            return "deleted" if result is not None else "not_found"
        if entity_type == "courses":
            result = await moodle.delete_courses([identifier])
            return "deleted" if result is not None else "not_found"
        if entity_type == "categories":
            cats = await moodle.get_categories(idnumber=identifier)
            if not cats:
                return "not_found"
            await moodle.delete_category(int(cats[0]["id"]))
            return "deleted"
        return "deleted"
    except Exception:
        if await _entity_exists(moodle, entity_type, identifier):
            raise
        return "deleted"


async def _process_single_item(item, batch, moodle, db):
    update_item(db, item.id, "processing")
    note = None

    if batch.action == "delete":
        outcome = await _delete_entity(moodle, batch.entity_type, item.identifier)
        if outcome == "not_found":
            note = _DELETE_NOT_FOUND_MESSAGE.get(
                batch.entity_type, "Entidad no encontrada en Moodle. Se omite (ya no existía)."
            )

    elif batch.action == "create":
        if batch.entity_type == "users":
            detail = item.detail or {}
            user_data = {
                "username": item.identifier,
                "firstname": detail.get("firstname", item.identifier),
                "lastname": detail.get("lastname", ""),
                "email": detail.get("email", f"{item.identifier}{settings.INSTITUTIONAL_EMAIL_DOMAIN}"),
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

    elif batch.action == "visibility":
        if batch.entity_type == "courses":
            detail = item.detail or {}
            visible = 1 if detail.get("visibility") == "show" else 0
            courses = await moodle.get_courses_by_field("shortname", item.identifier)
            if not courses:
                raise ValueError(f"Curso no encontrado en Moodle: {item.identifier}")
            await moodle.update_courses([{"id": int(courses[0]["id"]), "visible": visible}])

    update_item(db, item.id, "completed", note)
    update_batch_counts(db, batch.batch_id, completed=1)


async def _ensure_root_category(moodle: MoodleService):
    try:
        cats = await moodle.get_categories(idnumber="DISTANCIA")
        if not cats:
            await moodle.create_categories([{
                "name": settings.ROOT_CATEGORY_NAME,
                "idnumber": "DISTANCIA",
                "parent": 0,
            }])
            logger.info(f"Categoría raíz {settings.ROOT_CATEGORY_NAME} (DISTANCIA) creada automáticamente")
    except MoodleAPIError as e:
        logger.error(f"Error al crear categoría raíz {settings.ROOT_CATEGORY_NAME}: {e}")
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
