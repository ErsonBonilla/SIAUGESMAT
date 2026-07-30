"""
Tarea Celery para ejecutar consultas asíncronas contra la API REST de Moodle.
"""

import asyncio
import logging
import re
import time
from datetime import datetime

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.query_repo import (
    get_query,
    set_query_completed,
    set_query_failed,
    set_query_running,
)
from app.services.moodle_factory import get_moodle_service
from app.services.moodle_operations import MoodleService
from app.services.parsers.patterns import SIAUGESMAT_PATTERN, parse_shortname

logger = logging.getLogger(__name__)

SIAUGESMAT_RE = re.compile(SIAUGESMAT_PATTERN.pattern, re.IGNORECASE)

CAT_NAMES = {
    "IDE": "IDEAD",
    "URA": "Urabá",
    "SIB": "Sibaté",
    "FAC": "Facultad",
    "SIN": "Sin CAT",
}


def _semester_to_cutoff(semester: str) -> int:
    year = int(semester[:4])
    if semester[4] == "A":
        month, day = 1, 1
    else:
        month, day = 7, 1
    return int(datetime(year, month, day).timestamp())


async def _do_query(moodle: MoodleService, qr):
    params = qr.params or {}

    if qr.entity == "courses":
        search = params.get("search")
        status_filter = params.get("status", "all")
        raw = await moodle.get_courses()
        if search:
            q = search.strip().lower()
            raw = [c for c in raw if q in (c.get("shortname") or "").lower()]
        if status_filter == "unused_6months":
            cutoff = int(time.time()) - (6 * 30 * 24 * 3600)
            raw = [c for c in raw if c.get("timemodified", 0) and int(c.get("timemodified", 0)) < cutoff]
        pattern = params.get("pattern", "all")
        if pattern == "6segments":
            raw = [c for c in raw if (c.get("shortname") or "").count("_") == 5]
        elif pattern == "5segments":
            raw = [c for c in raw if (c.get("shortname") or "").count("_") == 4]
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

    elif qr.entity == "inactive_teachers":
        semester = params.get("semester", "")
        if not semester or len(semester) != 5 or semester[-1] not in ("A", "B"):
            raise ValueError("Se requiere un semestre válido (ej. 2026A).")
        cutoff = _semester_to_cutoff(semester)

        all_courses = await moodle.get_courses()
        siau_courses = [c for c in all_courses if SIAUGESMAT_RE.match(c.get("shortname", ""))]

        sem = asyncio.Semaphore(5)
        results = []

        async def process_course(course):
            async with sem:
                course_id = int(course["id"])
                try:
                    teachers = await moodle.get_enrolled_teachers_with_access(course_id)
                except Exception as e:
                    logger.warning(f"Error obteniendo profesores del curso {course.get('shortname')}: {e}")
                    return
                sn = course.get("shortname", "")
                parsed = parse_shortname(sn)
                program = parsed["cod_prog"] if parsed else ""
                cat_prefix = parsed["cat_prefix"] if parsed else ""
                cat_name = CAT_NAMES.get(cat_prefix, cat_prefix)
                for t in teachers:
                    last_access = t.get("lastcourseaccess", 0) or 0
                    if last_access > 0 and last_access >= cutoff:
                        continue
                    results.append({
                        "teacher_name": f'{t.get("firstname", "")} {t.get("lastname", "")}'.strip(),
                        "username": t.get("username", ""),
                        "email": t.get("email", ""),
                        "course_name": course.get("fullname", ""),
                        "course_shortname": sn,
                        "program": program,
                        "cat": cat_name,
                        "cat_prefix": cat_prefix,
                        "last_access": last_access,
                    })

        batch_size = 5
        for i in range(0, len(siau_courses), batch_size):
            batch = siau_courses[i:i + batch_size]
            await asyncio.gather(*[process_course(c) for c in batch])

        return results

    else:
        raise ValueError(f"Entidad desconocida: {qr.entity}")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, task_time_limit=600)
def execute_query(self, task_id: str):
    db = SessionLocal()
    qr = None
    try:
        set_query_running(db, task_id)
        qr = get_query(db, task_id)
        if not qr:
            logger.error(f"QueryResult {task_id} no encontrado")
            return

        moodle = get_moodle_service(qr.modalidad)

        async def _run_and_close():
            try:
                return await _do_query(moodle, qr)
            finally:
                await moodle.close()

        raw = asyncio.run(_run_and_close())

        set_query_completed(db, task_id, raw, len(raw))

    except Exception as exc:
        logger.exception(f"Fallo en query {task_id}")
        set_query_failed(db, task_id, str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    finally:
        db.close()
