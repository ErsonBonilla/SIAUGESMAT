"""
Tarea Celery para ejecutar consultas asíncronas contra la API REST de Moodle.
"""

import asyncio
import logging
import re
import time
from datetime import UTC, datetime

from app.celery_app import celery_app
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
from app.workers.utils import run_moodle_async

logger = logging.getLogger(__name__)

SIAUGESMAT_RE = re.compile(SIAUGESMAT_PATTERN.pattern, re.IGNORECASE)

CAT_NAMES = {
    "IDE": "IDEAD",
    "URA": "Urabá",
    "SIB": "Sibaté",
    "FAC": "Facultad",
    "SIN": "Sin CAT",
}


DEFAULT_INACTIVE_DAYS = 15
MAX_INACTIVE_DAYS = 30
DEFAULT_INACTIVE_MONTHS = 1
MAX_INACTIVE_MONTHS = 12
DEFAULT_INACTIVE_YEARS = 1


def _semester_to_cutoff(semester: str) -> int:
    year = int(semester[:4])
    if semester[4] == "A":
        month, day = 1, 1
    else:
        month, day = 7, 1
    return int(datetime(year, month, day, tzinfo=UTC).timestamp())


def _days_to_cutoff(days: int) -> int:
    return int(time.time()) - days * 86400


def _months_to_cutoff(months: int) -> int:
    return int(time.time()) - months * 30 * 86400


def _years_to_cutoff(years: int) -> int:
    return int(time.time()) - years * 365 * 86400


def _build_inactive_rows(teachers: list[dict], course: dict, cutoff: int) -> list[dict]:
    """Filtra y arma las filas de docentes inactivos (pura, sin I/O)."""
    now = int(time.time())
    sn = course.get("shortname", "")
    parsed = parse_shortname(sn)
    program = parsed["cod_prog"] if parsed else ""
    cat_prefix = parsed["cat_prefix"] if parsed else ""
    cat_name = CAT_NAMES.get(cat_prefix, cat_prefix)
    rows = []
    for t in teachers:
        last_access = t.get("lastcourseaccess", 0) or 0
        if last_access > 0 and last_access >= cutoff:
            continue
        rows.append({
            "teacher_name": f'{t.get("firstname", "")} {t.get("lastname", "")}'.strip(),
            "username": t.get("username", ""),
            "email": t.get("email", ""),
            "course_name": course.get("fullname", ""),
            "course_shortname": sn,
            "program": program,
            "cat": cat_name,
            "cat_prefix": cat_prefix,
            "last_access": last_access,
            "days_since_last_access": int((now - last_access) // 86400) if last_access > 0 else 0,
        })
    return rows


async def _filter_orphan_courses(moodle: MoodleService, courses: list[dict]) -> list[dict]:
    """Conserva solo cursos SIAUGESMAT sin docentes (editingteacher) matriculados."""
    siau_courses = [c for c in courses if SIAUGESMAT_RE.match(c.get("shortname", ""))]
    sem = asyncio.Semaphore(5)
    results = []

    async def check_course(course):
        async with sem:
            try:
                teachers = await moodle.get_enrolled_teachers_with_access(int(course["id"]))
            except Exception as e:
                logger.warning(f"Error obteniendo docentes del curso {course.get('shortname')}: {e}")
                return
            if not teachers:
                results.append(course)

    batch_size = 5
    for i in range(0, len(siau_courses), batch_size):
        batch = siau_courses[i:i + batch_size]
        await asyncio.gather(*[check_course(c) for c in batch])

    return results


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
        if params.get("orphan") in ("true", "1"):
            raw = await _filter_orphan_courses(moodle, raw)
        return raw

    if qr.entity == "categories":
        search = params.get("search")
        return await moodle.get_categories(idnumber=search)

    if qr.entity == "users":
        status_filter = params.get("status")
        search = params.get("search")

        raw = await moodle.search_users(search) if search else []

        if status_filter == "never_logged_in":
            raw = [u for u in raw if u.get("lastlogin", 1) == 0]
        return raw

    if qr.entity == "inactive_teachers":
        semester = params.get("semester", "")
        days = params.get("days")
        months = params.get("months")
        years = params.get("years")
        provided = sum([
            bool(semester and len(semester) == 5 and semester[-1] in ("A", "B")),
            days is not None,
            months is not None,
            years is not None,
        ])
        if provided != 1:
            raise ValueError(
                "Se requiere exactamente un corte: semestre (ej. 2026A), "
                "días, meses o años."
            )
        if semester:
            cutoff = _semester_to_cutoff(semester)
        elif days is not None:
            try:
                days = int(days)
            except (TypeError, ValueError):
                raise ValueError("'days' debe ser un número entero.") from None
            if days < 1 or days > MAX_INACTIVE_DAYS:
                raise ValueError(
                    f"'days' debe estar entre 1 y {MAX_INACTIVE_DAYS}."
                )
            cutoff = _days_to_cutoff(days)
        elif months is not None:
            try:
                months = int(months)
            except (TypeError, ValueError):
                raise ValueError("'months' debe ser un número entero.") from None
            if months < 1 or months > MAX_INACTIVE_MONTHS:
                raise ValueError(
                    f"'months' debe estar entre 1 y {MAX_INACTIVE_MONTHS}."
                )
            cutoff = _months_to_cutoff(months)
        else:
            try:
                years = int(years)
            except (TypeError, ValueError):
                raise ValueError("'years' debe ser un número entero.") from None
            if years < 1:
                raise ValueError("'years' debe ser al menos 1.")
            cutoff = _years_to_cutoff(years)

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
                results.extend(_build_inactive_rows(teachers, course, cutoff))

        batch_size = 5
        for i in range(0, len(siau_courses), batch_size):
            batch = siau_courses[i:i + batch_size]
            await asyncio.gather(*[process_course(c) for c in batch])

        return results

    raise ValueError(f"Entidad desconocida: {qr.entity}")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30, time_limit=3600, soft_time_limit=3540)
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

        raw = run_moodle_async(moodle, _do_query(moodle, qr))

        set_query_completed(db, task_id, raw, len(raw))

    except Exception as exc:
        logger.exception(f"Fallo en query {task_id}")
        set_query_failed(db, task_id, str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries) from exc

    finally:
        db.close()
