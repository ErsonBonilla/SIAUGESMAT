"""
Tareas Celery para operaciones masivas de creación y eliminación de entidades en Moodle.
"""

import logging

from app.celery_app import celery_app
from app.core.config import settings
from app.db.modelos import ItemOperacion
from app.db.sesion import SessionLocal
from app.repositories.repositorio_operaciones import (
    actualizar_conteos_lote,
    actualizar_item,
    completar_lote,
    obtener_items_pendientes,
    obtener_lote,
)
from app.services.errores_moodle import ErrorApiMoodle
from app.services.fabrica_moodle import obtener_servicio_moodle
from app.services.mensajes_error import traducir_error
from app.services.operaciones_moodle import ServicioMoodle
from app.services.roles import resolver_rol
from app.workers.utilidades import ejecutar_moodle_async

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.operations_tasks.process_operation_batch",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def procesar_lote_operacion(self, batch_id: str):
    db = SessionLocal()
    try:
        batch = obtener_lote(db, batch_id)
        if not batch:
            logger.error(f"Lote {batch_id} no encontrado")
            return

        moodle = obtener_servicio_moodle(batch.modalidad)
        items = obtener_items_pendientes(db, batch_id)

        async def _procesar_todos():
            if batch.tipo_entidad == "categories" and batch.accion == "create":
                await _asegurar_categoria_raiz(moodle)

            detenido_por_control = False
            for item in items:
                # Re-consultar batch por si fue pausado o cancelado
                try:
                    paused = (
                        db.query(ItemOperacion).filter_by(id_lote=batch_id, estado="paused").count()
                    )
                    cancelled = (
                        db.query(ItemOperacion)
                        .filter_by(id_lote=batch_id, estado="cancelled")
                        .count()
                    )
                    if paused > 0:
                        logger.info(
                            f"Lote {batch_id} pausado, deteniendo procesamiento ({paused} items)"
                        )
                        detenido_por_control = True
                        break
                    if cancelled > 0:
                        logger.info(
                            f"Lote {batch_id} cancelado, deteniendo procesamiento ({cancelled} items)"
                        )
                        detenido_por_control = True
                        break
                except TypeError as exc:
                    logger.warning(
                        f"Error al consultar pausa/cancelación del lote {batch_id}: {exc}"
                    )
                try:
                    await _procesar_item_unico(item, batch, moodle, db)
                except ErrorApiMoodle as e:
                    msg = _formatear_error_moodle(e, batch.tipo_entidad, item)
                    logger.exception(f"Error en {batch.tipo_entidad} '{item.identificador}': {msg}")
                    actualizar_item(db, item.id, "failed", msg)
                    actualizar_conteos_lote(db, batch_id, failed=1)
                except Exception as exc:
                    logger.exception(
                        f"Error en {batch.tipo_entidad} '{item.identificador}' (lote {batch_id})"
                    )
                    actualizar_item(db, item.id, "failed", traducir_error(exc))
                    actualizar_conteos_lote(db, batch_id, failed=1)
            return detenido_por_control

        detenido = ejecutar_moodle_async(moodle, _procesar_todos())

        if not detenido:
            completar_lote(db, batch_id)
        else:
            logger.info(f"Lote {batch_id} no completado: pausado o cancelado")

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


_DELETED_USER_ERROR_CODES = frozenset({"invaliduser", "invalidrecord"})


async def _entidad_existe(moodle, entity_type: str, identifier: str) -> bool:
    if entity_type == "users":
        try:
            return await moodle.obtener_usuario_por_username(identifier) is not None
        except ErrorApiMoodle as e:
            # Algunos Moodle (p. ej. tuaulavirtual) lanzan invaliduser en vez
            # de devolver una lista vacía cuando el usuario ya fue eliminado.
            # Se trata como "no existe": el borrado ya está consumado.
            if getattr(e, "codigo_error", None) in _DELETED_USER_ERROR_CODES:
                return False
            raise
    if entity_type == "courses":
        return bool(await moodle.obtener_cursos(shortname=identifier))
    if entity_type == "categories":
        return bool(await moodle.obtener_categorias(idnumber=identifier))
    return True


async def _eliminar_entidad(moodle, entity_type: str, identifier: str) -> str:
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
            result = await moodle.eliminar_usuarios([identifier])
            return "deleted" if result is not None else "not_found"
        if entity_type == "courses":
            result = await moodle.eliminar_cursos([identifier])
            return "deleted" if result is not None else "not_found"
        if entity_type == "categories":
            cats = await moodle.obtener_categorias(idnumber=identifier)
            if not cats:
                return "not_found"
            await moodle.eliminar_categoria(int(cats[0]["id"]))
            return "deleted"
        return "deleted"
    except ErrorApiMoodle as e:
        # core_user_delete_users (y su lookup previo) rechaza con invaliduser /
        # invalidrecord a los usuarios ya eliminados en Moodle (deleted=1). Como
        # el borrado ya está consumado, se omite en lugar de fallar.
        if entity_type == "users" and getattr(e, "codigo_error", None) in _DELETED_USER_ERROR_CODES:
            return "not_found"
        raise
    except Exception:
        if await _entidad_existe(moodle, entity_type, identifier):
            raise
        return "deleted"


async def _procesar_item_unico(item, batch, moodle, db):
    actualizar_item(db, item.id, "processing")
    note = None

    if batch.accion == "delete":
        outcome = await _eliminar_entidad(moodle, batch.tipo_entidad, item.identificador)
        if outcome == "not_found":
            note = _DELETE_NOT_FOUND_MESSAGE.get(
                batch.tipo_entidad, "Entidad no encontrada en Moodle. Se omite (ya no existía)."
            )

    elif batch.accion == "create":
        if batch.tipo_entidad == "users":
            detail = item.detalle or {}
            user_data = {
                "username": item.identificador,
                "firstname": detail.get("firstname", item.identificador),
                "lastname": detail.get("lastname", ""),
                "email": detail.get(
                    "email", f"{item.identificador}{settings.INSTITUTIONAL_EMAIL_DOMAIN}"
                ),
                "createpassword": True,
            }
            created = await moodle.crear_usuarios([user_data])

            role = detail.get("role1")
            if role and created and len(created) > 0:
                user_id = created[0].get("id")
                if user_id:
                    role_id = resolver_rol(str(role))
                    await moodle.asignar_rol(int(user_id), role_id)

        elif batch.tipo_entidad == "categories":
            detail = item.detalle or {}
            parent_idnumber = detail.get("parent") or "DISTANCIA"
            cat_data = {
                "name": item.identificador,
                "idnumber": detail.get("idnumber") or item.identificador,
                "parent": parent_idnumber,
            }
            if detail.get("description"):
                cat_data["description"] = detail["description"]
            if detail.get("visible") is not None:
                cat_data["visible"] = int(detail["visible"])
            await moodle.crear_categorias([cat_data])

    elif batch.accion == "visibility":
        if batch.tipo_entidad == "courses":
            detail = item.detalle or {}
            visible = 1 if detail.get("visibility") == "show" else 0
            courses = await moodle.obtener_cursos_por_campo("shortname", item.identificador)
            if not courses:
                raise ValueError(f"Curso no encontrado en Moodle: {item.identificador}")
            await moodle.actualizar_cursos([{"id": int(courses[0]["id"]), "visible": visible}])

    actualizar_item(db, item.id, "completed", note)
    actualizar_conteos_lote(db, batch.id_lote, completed=1)


async def _asegurar_categoria_raiz(moodle: ServicioMoodle):
    try:
        cats = await moodle.obtener_categorias(idnumber="DISTANCIA")
        if not cats:
            await moodle.crear_categorias(
                [
                    {
                        "name": settings.ROOT_CATEGORY_NAME,
                        "idnumber": "DISTANCIA",
                        "parent": 0,
                    }
                ]
            )
            logger.info(
                f"Categoría raíz {settings.ROOT_CATEGORY_NAME} (DISTANCIA) creada automáticamente"
            )
    except ErrorApiMoodle as e:
        logger.exception(f"Error al crear categoría raíz {settings.ROOT_CATEGORY_NAME}: {e}")
        raise


def _formatear_error_moodle(e: ErrorApiMoodle, entity_type: str, item) -> str:
    code = getattr(e, "codigo_error", None)
    detail = item.detalle or {}

    if code == "duplicateuser":
        return f"El usuario '{item.identificador}' ya existe en Moodle (username duplicado)."
    if code == "invalidemail":
        email = detail.get("email", "")
        return f"Email inválido '{email}' para el usuario '{item.identificador}'."
    if code == "emailnotallowed":
        email = detail.get("email", "")
        return f"El dominio del email '{email}' no está permitido en Moodle para '{item.identificador}'."
    if code == "duplicatecategory":
        return f"La categoría '{item.identificador}' ya existe en Moodle (idnumber duplicado)."
    if code == "cannotfindparentcategory":
        parent = detail.get("parent") or "DISTANCIA"
        return f"Categoría padre '{parent}' no encontrada en Moodle."
    if code == "invalidparameter":
        return f"Parámetro inválido para '{item.identificador}': {e}"
    return e.mensaje_espanol
