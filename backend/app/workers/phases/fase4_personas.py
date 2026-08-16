import logging
import uuid
from functools import wraps

from app.repositories.repositorio_operaciones import agregar_item, crear_lote
from app.services.fabrica_moodle import obtener_servicio_moodle
from app.workers.phases.comunes import (
    _adquirir_bloqueo_asesor,
    _existen_items_para_ejecucion,
    _obtener_conteos_pendientes,
)
from app.workers.utilidades import _ejecutar_async

logger = logging.getLogger(__name__)


def _envoltura_sincronizacion(async_fn):
    @wraps(async_fn)
    def wrapper(*args, **kwargs):
        return _ejecutar_async(async_fn(*args, **kwargs))

    return wrapper


async def _resolver_mapa_cursos(modalidad, all_sns):
    ms = obtener_servicio_moodle(modalidad)
    try:
        all_courses = await ms.obtener_cursos()
        course_map = {c["shortname"]: int(c["id"]) for c in all_courses if c.get("shortname")}
        course_fullname = {
            c["shortname"]: c.get("fullname", "") for c in all_courses if c.get("shortname")
        }
        missing = [sn for sn in all_sns if sn and sn not in course_map]
        if missing:
            BATCH = 5
            for i in range(0, len(missing), BATCH):
                chunk = missing[i : i + BATCH]
                try:
                    resolved = await ms.obtener_cursos_por_shortnames(chunk)
                    for c in resolved:
                        if c.get("shortname"):
                            course_map[c["shortname"]] = int(c["id"])
                            course_fullname[c["shortname"]] = c.get("fullname", "")
                except Exception as e:
                    logger.warning(f"Falló resolver cursos por shortnames (lote): {e}")
                    for sn in chunk:
                        try:
                            courses = await ms.obtener_cursos_por_campo("shortname", sn)
                            if courses and courses[0].get("id"):
                                course_map[sn] = int(courses[0]["id"])
                                course_fullname[sn] = courses[0].get("fullname", "")
                        except Exception:
                            logger.debug(f"No se pudo resolver curso {sn} por field fallback")
        return course_map, course_fullname
    finally:
        await ms.close()


async def _resolver_respaldo(modalidad, all_sns):
    ms = obtener_servicio_moodle(modalidad)
    try:
        fallback_map = {}
        fallback_fullname = {}
        BATCH = 5
        for i in range(0, len(all_sns), BATCH):
            chunk = all_sns[i : i + BATCH]
            try:
                resolved = await ms.obtener_cursos_por_shortnames(chunk)
                for c in resolved:
                    if c.get("shortname"):
                        fallback_map[c["shortname"]] = int(c["id"])
                        fallback_fullname[c["shortname"]] = c.get("fullname", "")
            except Exception as e:
                logger.warning(f"Falló resolver cursos por shortnames (fallback): {e}")
                for sn in chunk:
                    try:
                        courses = await ms.obtener_cursos_por_campo("shortname", sn)
                        if courses and courses[0].get("id"):
                            fallback_map[sn] = int(courses[0]["id"])
                            fallback_fullname[sn] = courses[0].get("fullname", "")
                    except Exception:
                        logger.debug(f"No se pudo resolver curso {sn} en fallback")
        return fallback_map, fallback_fullname
    finally:
        await ms.close()


async def _crear_items_fase4_async(db, execution_id, ctx_data, modalidad) -> dict[str, int]:
    if _existen_items_para_ejecucion(db, execution_id, "4"):
        pending = _obtener_conteos_pendientes(db, execution_id, "4")
        if pending:
            logger.info(
                f"Items FASE 4 ya existen con {sum(pending.values())} pendientes, retomando"
            )
            return pending
        logger.info("Items FASE 4 ya existen y todos procesados, saltando creación")
        return {}
    if not _adquirir_bloqueo_asesor(db, execution_id, "4"):
        logger.info(
            f"Lock FASE 4 ya tomado para ejecución {execution_id}, otro worker crea los items"
        )
        return {}

    counts: dict[str, int] = {}
    usuarios_a_crear = ctx_data.get("users_to_create", [])
    resolved_enrolments = ctx_data.get("resolved_enrolments", [])

    def _id_lote(suffix):
        return f"etl_4_{suffix}_{execution_id}"

    if usuarios_a_crear:
        batch = crear_lote(
            db, _id_lote("users"), "users", "create", len(usuarios_a_crear), modalidad
        )
        count = 0
        for user in usuarios_a_crear:
            username = (
                user.get("email", "").split("@")[0]
                if user.get("email")
                else user.get("username", str(uuid.uuid4()))
            )
            detail = {
                "action": "create_user",
                "execution_id": execution_id,
                "modalidad": modalidad,
                "username": user.get("username", username),
                "firstname": user.get("firstname", ""),
                "lastname": user.get("lastname", ""),
                "email": user.get("email", ""),
                "has_password": bool(user.get("password")),
                "cedula": user.get("cedula", ""),
                "city": user.get("city", ""),
                "description": user.get("description", ""),
                "email_personal": user.get("email_personal", ""),
            }
            identifier = user.get("username", username)
            agregar_item(db, batch.id_lote, identifier, detail)
            count += 1
        counts["create_users"] = count

    if resolved_enrolments:
        batch = crear_lote(
            db, _id_lote("enrol"), "enrolments", "enrol", len(resolved_enrolments), modalidad
        )
        count = 0

        users_by_username = {u["username"]: u for u in ctx_data.get("users", [])}

        all_sns = list(
            {
                enrol.get("course_shortname", "")
                for enrol in resolved_enrolments
                if enrol.get("course_shortname")
            }
        )
        try:
            course_map, course_fullname = await _resolver_mapa_cursos(modalidad, all_sns)
        except Exception as e:
            logger.warning(f"Error resolviendo course_map global: {e}, intentando por shortname")
            try:
                course_map, course_fullname = await _resolver_respaldo(modalidad, all_sns)
            except Exception as e2:
                logger.warning(f"Error resolviendo course_map fallback: {e2}, usando map vacío")
                course_map, course_fullname = {}, {}

        for enrol in resolved_enrolments:
            username = enrol.get("username", "")
            course_sn = enrol.get("course_shortname", "")
            course_id = course_map.get(course_sn)
            detail = {
                "action": "enrol",
                "execution_id": execution_id,
                "modalidad": modalidad,
                "course_shortname": course_sn,
                "fullname": course_fullname.get(course_sn, ""),
                "_course_id": course_id,
            }
            user_data = users_by_username.get(username, {})
            if user_data:
                detail["firstname"] = user_data.get("firstname", "")
                detail["lastname"] = user_data.get("lastname", "")
                detail["email"] = user_data.get("email", "")
            agregar_item(db, batch.id_lote, username, detail)
            count += 1
        counts["enrol"] = count

    db.commit()
    return counts


_create_phase4_items = _envoltura_sincronizacion(_crear_items_fase4_async)
