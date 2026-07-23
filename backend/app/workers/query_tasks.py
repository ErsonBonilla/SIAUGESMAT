"""
Tarea Celery para ejecutar consultas asíncronas contra la API REST de Moodle.
"""

import asyncio
import logging
import time

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.query_repo import (
    get_query,
    set_query_completed,
    set_query_failed,
    set_query_running,
)
from app.services.moodle import MoodleService

logger = logging.getLogger(__name__)


async def _do_query(moodle: MoodleService, qr):
    params = qr.params or {}

    if qr.entity == "courses":
        search = params.get("search")
        status_filter = params.get("status", "all")
        raw = await moodle.get_courses_by_field("shortname", search) if search else await moodle.get_courses()
        if status_filter == "unused_6months":
            cutoff = int(time.time()) - (6 * 30 * 24 * 3600)
            raw = [c for c in raw if c.get("timemodified", 0) and int(c.get("timemodified", 0)) < cutoff]
        return raw

    elif qr.entity == "categories":
        search = params.get("search")
        return await moodle.get_categories(idnumber=search)

    elif qr.entity == "users":
        role = params.get("role", "all")
        status_filter = params.get("status")
        search = params.get("search")

        raw = await moodle.get_users_by_role("editingteacher") if role == "professor" else await moodle.get_all_users()

        if status_filter == "never_logged_in":
            raw = [u for u in raw if u.get("lastlogin", 1) == 0]
        if search:
            q = search.lower()
            raw = [u for u in raw
                   if q in (u.get("username") or "").lower()
                   or q in (u.get("email") or "").lower()
                   or q in (u.get("firstname") or "").lower()
                   or q in (u.get("lastname") or "").lower()]
        return raw

    else:
        raise ValueError(f"Entidad desconocida: {qr.entity}")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, task_time_limit=300)
def execute_query(self, task_id: str):
    db = SessionLocal()
    qr = None
    try:
        set_query_running(db, task_id)
        qr = get_query(db, task_id)
        if not qr:
            logger.error(f"QueryResult {task_id} no encontrado")
            return

        config = settings.get_moodle_config(qr.modalidad)
        moodle = MoodleService(
            token=config["token"],
            base_url=config["url"],
            version=config["version"],
        )

        try:
            raw = asyncio.run(_do_query(moodle, qr))
        finally:
            asyncio.run(moodle.close())

        set_query_completed(db, task_id, raw, len(raw))

    except Exception as exc:
        logger.exception(f"Fallo en query {task_id}")
        set_query_failed(db, task_id, str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    finally:
        db.close()
