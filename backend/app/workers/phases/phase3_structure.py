import asyncio
import logging

from celery import chord

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.execution_repo import (
    clear_chord_active,
    get_execution,
    set_chord_active,
)
from app.repositories.log_repo import save_log
from app.repositories.operation_repo import add_item, create_batch
from app.services.moodle_factory import get_moodle_service
from app.workers.phases.common import (
    MoodleOverloadedError,
    _acquire_advisory_lock,
    _get_pending_counts,
    _get_pending_items,
    _items_exist_for_execution,
    on_phase_items_done,
)
from app.workers.phases.item_task import _refresh_phase_progress, process_etl_item
from app.workers.utils import _run_async, reset_stuck_items

logger = logging.getLogger(__name__)


def _create_phase3_items(db, execution_id, ctx_data, comparison, modalidad) -> dict[str, int]:
    if _items_exist_for_execution(db, execution_id, "3"):
        pending = _get_pending_counts(db, execution_id, "3")
        if pending:
            logger.info(
                f"Items FASE 3 ya existen con {sum(pending.values())} pendientes, retomando"
            )
            return pending
        logger.info("Items FASE 3 ya existen y todos procesados, saltando creación")
        return {}
    if not _acquire_advisory_lock(db, execution_id, "3"):
        logger.info(
            f"Lock FASE 3 ya tomado para ejecución {execution_id}, otro worker crea los items"
        )
        return {}

    counts: dict[str, int] = {}
    courses = {c["shortname"]: c for c in ctx_data.get("courses", [])}
    existing_by_sn = {c["shortname"]: c for c in ctx_data.get("existing_courses", [])}
    users_by_username = {u["username"]: u for u in ctx_data.get("users", [])}

    def _batch_id(suffix):
        return f"etl_3_{suffix}_{execution_id}"

    def _add_items(identifiers, action, batch_suffix=None):
        if not identifiers:
            return
        batch_suffix = batch_suffix or action
        batch = create_batch(
            db, _batch_id(batch_suffix), "courses", action, len(identifiers), modalidad
        )
        count = 0
        for identifier in identifiers:
            detail = {"action": action, "execution_id": execution_id, "modalidad": modalidad}
            if isinstance(identifier, dict):
                detail.update({k: v for k, v in identifier.items() if k != "action"})
                identifier = identifier.get(
                    "shortname", identifier.get("identifier", str(identifier))
                )
            add_item(db, batch.batch_id, str(identifier), detail)
            count += 1
        counts[action] = count

    _add_items(comparison.get("to_delete", []), "delete")
    _add_items(comparison.get("to_activate", []), "activate")
    _add_items(comparison.get("to_hide", []), "hide")

    rename_items = comparison.get("to_update", [])
    if rename_items:
        batch = create_batch(
            db, _batch_id("rename"), "courses", "rename", len(rename_items), modalidad
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
            add_item(db, batch.batch_id, sn, detail)
            count += 1
        counts["rename"] = count

    create_items = comparison.get("to_create", [])
    if create_items:
        _create_template_cache = {}

        async def _resolve_templates():
            ms = get_moodle_service(modalidad)
            try:

                async def _resolve_single(item):
                    sn = item["shortname"]
                    course_data = courses.get(sn, {})
                    template = item.get("template_shortname") or course_data.get("templatecourse")
                    template_id = None
                    if template and template.startswith("PORTAFOLIO_"):
                        if template not in _create_template_cache:
                            try:
                                existing = await ms.get_courses(shortname=template)
                                _create_template_cache[template] = (
                                    existing[0]["id"] if existing else None
                                )
                            except Exception:
                                _create_template_cache[template] = None
                        template_id = _create_template_cache.get(template)
                    if not template_id:
                        fallback = settings.DEFAULT_COURSE_TEMPLATE
                        if fallback and fallback not in _create_template_cache:
                            try:
                                fb = await ms.get_courses(shortname=fallback)
                                _create_template_cache[fallback] = fb[0]["id"] if fb else None
                            except Exception:
                                _create_template_cache[fallback] = None
                        template_id = _create_template_cache.get(fallback) if fallback else None
                        if template and template.startswith("PORTAFOLIO_"):
                            save_log(
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

                return await asyncio.gather(*[_resolve_single(item) for item in create_items])
            finally:
                await ms.close()

        try:
            resolved = _run_async(_resolve_templates())
        except Exception as e:
            logger.warning(f"Error resolviendo templates: {e}, se usarán sin template")
            resolved = [
                (item["shortname"], courses.get(item["shortname"], {}), None, item)
                for item in create_items
            ]

        batch = create_batch(
            db, _batch_id("create"), "courses", "create", len(create_items), modalidad
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
            add_item(db, batch.batch_id, sn, detail)
            count += 1
        counts["create"] = count

    db.commit()
    return counts


def _launch_delete_chord(execution_id, delete_items):
    task_ids = [process_etl_item.si(item.id) for item in delete_items]
    _mark_delete_chord_active(execution_id)
    chord(task_ids)(on_delete_items_done.s(execution_id=execution_id))


def _mark_delete_chord_active(execution_id):
    """Marca el chord de deletes como activo (para el sweeper)."""
    db = SessionLocal()
    try:
        set_chord_active(db, execution_id)
    except Exception:
        logger.exception(f"No se pudo marcar chord de deletes activo para ejecución {execution_id}")
    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(MoodleOverloadedError,),
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    retry_backoff_max=60,
)
def on_delete_items_done(self, results, execution_id):
    db = SessionLocal()
    try:
        execution = get_execution(db, execution_id)
        if not execution or execution.status in ("paused", "cancelled"):
            return

        clear_chord_active(db, execution_id)

        reset_stuck_items(
            db,
            batch_id_prefix="etl_3_%",
            execution_id=execution_id,
            increment_attempt=True,
        )

        pending_deletes = _get_pending_items(db, execution_id, "3", "delete")
        if pending_deletes:
            # Safety cap: items con >= 3 intentos se marcan como failed
            max_attempt = 3
            over_limit = [p for p in pending_deletes if (p.attempt or 0) >= max_attempt]
            if over_limit:
                logger.error(
                    f"FASE 3: {len(over_limit)} deletes con >= {max_attempt} intentos, "
                    f"marcando como failed para evitar loop"
                )
                for p in over_limit:
                    p.status = "failed"
                    p.error_message = f"Máximo de {max_attempt} intentos alcanzado"
                db.commit()
                pending_deletes = [p for p in pending_deletes if (p.attempt or 0) < max_attempt]

        if pending_deletes:
            logger.warning(
                f"FASE 3: {len(pending_deletes)} deletes pendientes tras chord, relanzando"
            )
            _launch_delete_chord(execution_id, pending_deletes)
            return

        _refresh_phase_progress(execution_id, db=db)
        structure_items = _get_pending_items(db, execution_id, "3", "structure")
        if structure_items:
            from app.workers.phases.common import _launch_items_chord

            _launch_items_chord(execution_id, structure_items)
        else:
            on_phase_items_done.delay([], execution_id, "3")
    except Exception as e:
        logger.exception(f"Error en on_delete_items_done: {e}")
        raise
    finally:
        db.close()
