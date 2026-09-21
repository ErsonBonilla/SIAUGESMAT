import asyncio
import logging

from celery import chord

from app.celery_app import celery_app
from app.core.config import settings
from app.db.sesion import SessionLocal
from app.repositories.repositorio_ejecuciones import (
    limpiar_chord_activo,
    marcar_chord_activo,
    obtener_ejecucion,
)
from app.repositories.repositorio_operaciones import agregar_item, crear_lote
from app.repositories.repositorio_registros import guardar_log
from app.services.fabrica_moodle import obtener_servicio_moodle
from app.workers.phases.comunes import (
    ErrorMoodleSobrecargado,
    _adquirir_bloqueo_asesor,
    _existen_items_para_ejecucion,
    _obtener_conteos_pendientes,
    _obtener_items_pendientes,
    _reiniciar_items_fallidos,
    _sincronizar_conteos_lote,
    al_terminar_items_fase,
)
from app.workers.phases.tarea_item import _refrescar_progreso_fase, procesar_item_etl
from app.workers.utilidades import _ejecutar_async, reiniciar_items_atascados

logger = logging.getLogger(__name__)


def _crear_items_fase3(db, execution_id, ctx_data, comparison, modalidad) -> dict[str, int]:
    if _existen_items_para_ejecucion(db, execution_id, "3"):
        pending = _obtener_conteos_pendientes(db, execution_id, "3")
        if pending:
            logger.info(
                f"Items FASE 3 ya existen con {sum(pending.values())} pendientes, retomando"
            )
            return pending
        logger.info("Items FASE 3 ya existen y todos procesados, saltando creación")
        return {}
    if not _adquirir_bloqueo_asesor(db, execution_id, "3"):
        logger.info(
            f"Lock FASE 3 ya tomado para ejecución {execution_id}, otro worker crea los items"
        )
        return {}

    counts: dict[str, int] = {}
    courses = {c["shortname"]: c for c in ctx_data.get("courses", [])}
    existing_by_sn = {c["shortname"]: c for c in ctx_data.get("existing_courses", [])}
    users_by_username = {u["username"]: u for u in ctx_data.get("users", [])}

    def _id_lote(suffix):
        return f"etl_3_{suffix}_{execution_id}"

    def _agregar_items(identifiers, action, batch_suffix=None):
        if not identifiers:
            return
        batch_suffix = batch_suffix or action
        batch = crear_lote(
            db, _id_lote(batch_suffix), "courses", action, len(identifiers), modalidad
        )
        count = 0
        for identifier in identifiers:
            detail = {"action": action, "execution_id": execution_id, "modalidad": modalidad}
            if isinstance(identifier, dict):
                detail.update({k: v for k, v in identifier.items() if k != "action"})
                identifier = identifier.get(
                    "shortname", identifier.get("identifier", str(identifier))
                )
            agregar_item(db, batch.id_lote, str(identifier), detail)
            count += 1
        counts[action] = count

    _agregar_items(comparison.get("to_delete", []), "delete")
    _agregar_items(comparison.get("to_activate", []), "activate")
    _agregar_items(comparison.get("to_hide", []), "hide")

    rename_items = comparison.get("to_update", [])
    if rename_items:
        batch = crear_lote(
            db, _id_lote("rename"), "courses", "rename", len(rename_items), modalidad
        )
        count = 0
        for item in rename_items:
            sn = item["shortname"]
            course_data = courses.get(sn, {})
            detail = {
                "action": "rename",
                "execution_id": execution_id,
                "modalidad": modalidad,
                "old_shortname": item.get("old_shortname", sn),
                "old_fullname": existing_by_sn.get(item.get("old_shortname", sn), {}).get(
                    "fullname", ""
                ),
                "fullname": course_data.get("fullname", sn),
                "reason": item.get("reason", ""),
                "professor": item.get("professor", ""),
                "reactivate": item.get("reactivate", False),
                "age_seconds": item.get("age_seconds"),
            }
            agregar_item(db, batch.id_lote, sn, detail)
            count += 1
        counts["rename"] = count

    create_items = comparison.get("to_create", [])
    if create_items:
        _create_template_cache = {}
        missing_templates: set[str] = set()

        async def _resolver_plantillas():
            ms = obtener_servicio_moodle(modalidad)
            try:

                async def _resolver_unico(item):
                    sn = item["shortname"]
                    course_data = courses.get(sn, {})
                    template = item.get("template_shortname") or course_data.get("templatecourse")
                    template_id = None
                    if template and template.startswith("PORTAFOLIO_"):
                        if template not in _create_template_cache:
                            try:
                                existing = await ms.obtener_cursos(shortname=template)
                                _create_template_cache[template] = (
                                    existing[0]["id"] if existing else None
                                )
                            except Exception as e:
                                logger.warning(f"No se pudo resolver template {template}: {e}")
                                _create_template_cache[template] = None
                        template_id = _create_template_cache.get(template)
                    if not template_id:
                        fallback = settings.DEFAULT_COURSE_TEMPLATE
                        if fallback and fallback not in _create_template_cache:
                            try:
                                fb = await ms.obtener_cursos(shortname=fallback)
                                _create_template_cache[fallback] = fb[0]["id"] if fb else None
                            except Exception as e:
                                logger.warning(
                                    f"No se pudo resolver template fallback {fallback}: {e}"
                                )
                                _create_template_cache[fallback] = None
                        template_id = _create_template_cache.get(fallback) if fallback else None
                        if template and template.startswith("PORTAFOLIO_"):
                            missing_templates.add(template)
                            guardar_log(
                                db,
                                execution_id,
                                "3",
                                "template_not_found",
                                sn,
                                {
                                    "fullname": course_data.get("fullname", ""),
                                    "template_shortname": template,
                                    "fallback": fallback if template_id else "",
                                },
                            )
                    return sn, course_data, template_id, item

                return await asyncio.gather(*[_resolver_unico(item) for item in create_items])
            finally:
                await ms.cerrar()

        try:
            resolved = _ejecutar_async(_resolver_plantillas())
        except Exception as e:
            logger.warning(f"Error resolviendo templates: {e}, se usarán sin template")
            resolved = [
                (item["shortname"], courses.get(item["shortname"], {}), None, item)
                for item in create_items
            ]

        if missing_templates:
            ex = obtener_ejecucion(db, execution_id)
            if ex:
                metrics = ex.metricas or {}
                metrics["templates_missing"] = len(missing_templates)
                metrics["templates_missing_examples"] = sorted(missing_templates)[:20]
                ex.metricas = metrics
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(ex, "metricas")
                db.commit()
            logger.warning(
                f"Ejecución {execution_id}: {len(missing_templates)} plantillas "
                f"PORTAFOLIO_ no encontradas en Moodle"
            )

        batch = crear_lote(
            db, _id_lote("create"), "courses", "create", len(create_items), modalidad
        )
        count = 0
        for sn, course_data, template_id, item in resolved:
            detail = {
                "action": "create",
                "execution_id": execution_id,
                "modalidad": modalidad,
                "fullname": course_data.get("fullname", sn),
                "category_idnumber": course_data.get("category_idnumber", ""),
                "template_id": template_id,
            }
            for key, value in item.items():
                if key in ("shortname", "template_shortname"):
                    continue
                detail.setdefault(key, value)
            prof = users_by_username.get(item.get("professor", ""), {})
            if prof:
                detail.setdefault("firstname", prof.get("firstname", ""))
                detail.setdefault("lastname", prof.get("lastname", ""))
            agregar_item(db, batch.id_lote, sn, detail)
            count += 1
        counts["create"] = count

    db.commit()
    return counts


def _lanzar_chord_eliminacion(execution_id, delete_items):
    task_ids = [procesar_item_etl.si(item.id) for item in delete_items]
    _marcar_chord_eliminacion_activo(execution_id)
    chord(task_ids)(al_terminar_items_eliminacion.s(execution_id=execution_id))


def _marcar_chord_eliminacion_activo(execution_id):
    """Marca el chord de deletes como activo (para el sweeper)."""
    db = SessionLocal()
    try:
        marcar_chord_activo(db, execution_id)
    except Exception:
        logger.exception(f"No se pudo marcar chord de deletes activo para ejecución {execution_id}")
    finally:
        db.close()


@celery_app.task(
    name="app.workers.phases.phase3_structure.on_delete_items_done",
    bind=True,
    autoretry_for=(ErrorMoodleSobrecargado,),
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    retry_backoff_max=60,
)
def al_terminar_items_eliminacion(self, results, execution_id):
    db = SessionLocal()
    try:
        execution = obtener_ejecucion(db, execution_id)
        if not execution or execution.estado in ("paused", "cancelled"):
            return

        limpiar_chord_activo(db, execution_id)

        _reiniciar_items_fallidos(db, execution_id, "3")

        reiniciar_items_atascados(
            db,
            batch_id_prefix="etl_3_%",
            execution_id=execution_id,
            increment_attempt=True,
        )

        pending_deletes = _obtener_items_pendientes(db, execution_id, "3", "delete")
        if pending_deletes:
            # Safety cap: items con >= 3 intentos se marcan como failed
            max_attempt = 3
            over_limit = [p for p in pending_deletes if (p.intento or 0) >= max_attempt]
            if over_limit:
                logger.error(
                    f"FASE 3: {len(over_limit)} deletes con >= {max_attempt} intentos, "
                    f"marcando como failed para evitar loop"
                )
                for p in over_limit:
                    p.estado = "failed"
                    p.mensaje_error = f"Máximo de {max_attempt} intentos alcanzado"
                db.commit()
                pending_deletes = [p for p in pending_deletes if (p.intento or 0) < max_attempt]

        if pending_deletes:
            logger.warning(
                f"FASE 3: {len(pending_deletes)} deletes pendientes tras chord, relanzando"
            )
            _lanzar_chord_eliminacion(execution_id, pending_deletes)
            return

        _refrescar_progreso_fase(execution_id, db=db)
        _sincronizar_conteos_lote(db, execution_id)
        structure_items = _obtener_items_pendientes(db, execution_id, "3", "structure")
        if structure_items:
            from app.workers.phases.comunes import _lanzar_chord_items

            _lanzar_chord_items(execution_id, structure_items)
        else:
            al_terminar_items_fase.delay([], execution_id, "3")
    except Exception as e:
        logger.exception(f"Error en on_delete_items_done: {e}")
        raise
    finally:
        db.close()
