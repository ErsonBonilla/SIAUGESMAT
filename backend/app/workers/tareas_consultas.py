"""
Tarea Celery para ejecutar consultas asíncronas contra la API REST de Moodle.
"""

import asyncio
import logging
import re
import time
from datetime import UTC, datetime

from app.celery_app import celery_app
from app.db.modelos import RegistroEjecucion
from app.db.sesion import SessionLocal
from app.pipeline.categorias import (
    obtener_ids_subarbol_idead,
    resolver_jerarquia_subcategorias,
)
from app.pipeline.nombres_cortos import SIAUGESMAT_PATTERN, parsear_shortname
from app.pipeline.observatorio import construir_censo_observatorio
from app.repositories.repositorio_consultas import (
    marcar_consulta_completada,
    marcar_consulta_en_ejecucion,
    marcar_consulta_fallida,
    obtener_consulta,
)
from app.services.fabrica_moodle import obtener_servicio_moodle
from app.services.operaciones_moodle import ServicioMoodle
from app.workers.utilidades import ejecutar_moodle_async

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


def _semestre_a_corte(semester: str) -> int:
    year = int(semester[:4])
    if semester[4] == "A":
        month, day = 1, 1
    else:
        month, day = 7, 1
    return int(datetime(year, month, day, tzinfo=UTC).timestamp())


def _dias_hasta_corte(days: int) -> int:
    return int(time.time()) - days * 86400


def _meses_hasta_corte(months: int) -> int:
    return int(time.time()) - months * 30 * 86400


def _anios_hasta_corte(years: int) -> int:
    return int(time.time()) - years * 365 * 86400


def _parsear_corte(params: dict, *, allow_semester: bool = True) -> int:
    """Valida que se provea exactamente un corte temporal y devuelve su timestamp.

    Acepta días (1-30), meses (1-12), años (>=1) y, si ``allow_semester=True``,
    semestre ("2025A"/"2025B").
    """
    semester = params.get("semester", "")
    days = params.get("days")
    months = params.get("months")
    years = params.get("years")
    if not allow_semester and semester:
        raise ValueError("Se requiere seleccionar el tiempo en días, meses o años.")
    provided = sum(
        [
            bool(
                allow_semester
                and isinstance(semester, str)
                and len(semester) == 5
                and semester[:4].isdigit()
                and semester[-1] in ("A", "B")
            ),
            days is not None,
            months is not None,
            years is not None,
        ]
    )
    if provided != 1:
        if not allow_semester:
            raise ValueError("Se requiere exactamente un corte: días, meses o años.")
        raise ValueError(
            "Se requiere exactamente un corte: semestre (ej. 2026A), días, meses o años."
        )
    if semester:
        return _semestre_a_corte(semester)
    if days is not None:
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValueError("El número de días debe ser un número entero.") from None
        if days < 1 or days > MAX_INACTIVE_DAYS:
            raise ValueError(f"El número de días debe estar entre 1 y {MAX_INACTIVE_DAYS}.")
        return _dias_hasta_corte(days)
    if months is not None:
        try:
            months = int(months)
        except (TypeError, ValueError):
            raise ValueError("El número de meses debe ser un número entero.") from None
        if months < 1 or months > MAX_INACTIVE_MONTHS:
            raise ValueError(f"El número de meses debe estar entre 1 y {MAX_INACTIVE_MONTHS}.")
        return _meses_hasta_corte(months)
    try:
        years = int(years)
    except (TypeError, ValueError):
        raise ValueError("El número de años debe ser un número entero.") from None
    if years < 1:
        raise ValueError("El número de años debe ser al menos 1.")
    return _anios_hasta_corte(years)


def _construir_filas_inactivos(
    teachers: list[dict],
    course: dict,
    cutoff: int,
    categorias: list[dict] | None = None,
    *,
    now: int | None = None,
) -> list[dict]:
    """Filtra y arma las filas de docentes inactivos (pura, sin I/O)."""
    if now is None:
        now = int(time.time())
    sn = course.get("shortname", "")
    parsed = parsear_shortname(sn)
    program = (parsed["cod_prog"] or "") if parsed else ""
    cat_prefix = (parsed["cat_prefix"] or "") if parsed else ""
    category_id = int(course.get("categoryid") or course.get("category") or 0)
    jerarquia = resolver_jerarquia_subcategorias(
        category_id,
        categorias or [],
        parsed,
        CAT_NAMES,
    )
    rows = []
    for t in teachers:
        last_access = t.get("lastcourseaccess", 0) or 0
        if last_access > 0 and last_access >= cutoff:
            continue
        rows.append(
            {
                "cat_shortname": jerarquia["cat_shortname"],
                "cat_name": jerarquia["cat_name"],
                "semester_shortname": jerarquia["semester_shortname"],
                "semester_name": jerarquia["semester_name"],
                "program_shortname": jerarquia["program_shortname"],
                "program_name": jerarquia["program_name"],
                "course_shortname": sn,
                "course_name": course.get("fullname", ""),
                "username": t.get("username", ""),
                "teacher_name": f"{t.get('firstname', '')} {t.get('lastname', '')}".strip(),
                "email": t.get("email", ""),
                "last_access": last_access,
                "days_since_last_access": int((now - last_access) // 86400)
                if last_access > 0
                else 0,
                "program": program,
                "cat": jerarquia["cat_name"],
                "cat_prefix": cat_prefix,
            }
        )
    return rows


async def _filtrar_cursos_huerfanos(moodle: ServicioMoodle, courses: list[dict]) -> list[dict]:
    """Conserva solo cursos SIAUGESMAT sin docentes (editingteacher) matriculados."""
    siau_courses = [c for c in courses if SIAUGESMAT_RE.match(c.get("shortname", ""))]
    sem = asyncio.Semaphore(5)
    results = []

    async def verificar_curso(course):
        async with sem:
            try:
                teachers = await moodle.obtener_docentes_matriculados_con_acceso(int(course["id"]))
            except Exception as e:
                logger.warning(
                    f"Error obteniendo docentes del curso {course.get('shortname')}: {e}"
                )
                return
            if not teachers:
                results.append(course)

    batch_size = 5
    for i in range(0, len(siau_courses), batch_size):
        batch = siau_courses[i : i + batch_size]
        await asyncio.gather(*[verificar_curso(c) for c in batch])

    return results


def _obtener_todos_usuarios_conocidos() -> list:
    """Usernames que la app ha creado o matriculado, sin límite de tiempo."""
    db = SessionLocal()
    try:
        rows = (
            db.query(RegistroEjecucion.identificador)
            .filter(RegistroEjecucion.accion.in_(["enrolment_ok", "user_created_createpassword"]))
            .distinct()
            .order_by(RegistroEjecucion.identificador)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()


def _normalizar_correo(email: str) -> str:
    """Normaliza un correo para agrupar: minúsculas y sin espacios."""
    return (email or "").strip().lower()


def _agrupar_usuarios_por_correo(users: list[dict]) -> dict[str, list[dict]]:
    """Agrupa usuarios por correo normalizado, ignorando correos vacíos."""
    by_email: dict[str, list[dict]] = {}
    for u in users:
        email = _normalizar_correo(u.get("email", ""))
        if not email:
            continue
        by_email.setdefault(email, []).append(u)
    return by_email


def _construir_filas_correos_duplicados(by_email: dict[str, list[dict]]) -> list[dict]:
    """Convierte los grupos en una fila por usuario (solo correos con más de una cuenta)."""
    rows = []
    for email, users in by_email.items():
        if len(users) <= 1:
            continue
        deduped: dict[int, dict] = {}
        for u in users:
            deduped.setdefault(int(u.get("id", 0)), u)
        account_list = list(deduped.values())
        for u in account_list:
            rows.append(
                {
                    "email": email,
                    "username": u.get("username", ""),
                    "firstname": u.get("firstname", ""),
                    "lastname": u.get("lastname", ""),
                    "user_id": u.get("id", ""),
                    "duplicate_count": len(account_list),
                }
            )

    def _id_sort_key(val) -> int:
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    rows.sort(key=lambda r: (r["email"], _id_sort_key(r["user_id"])))
    return rows


async def _consultar_correos_duplicados(moodle: ServicioMoodle) -> list[dict]:
    """Correos con más de un usuario en Moodle.

    Moodle 3.9 no permite listar todos los usuarios por webservice, así que se
    siembra el escaneo con dos fuentes (logs de la app + matriculados en cursos
    SIAUGESMAT) y luego se re-consulta cada correo candidato en Moodle
    (core_user_get_users_by_field) para capturar TODAS las cuentas que lo
    comparten, incluidas las que la app nunca tocó.
    """
    seed_emails: set[str] = set()

    usernames = _obtener_todos_usuarios_conocidos()
    for i in range(0, len(usernames), 100):
        batch = usernames[i : i + 100]
        try:
            users = await moodle.obtener_usuarios("username", batch)
        except Exception as e:
            logger.warning(f"Error consultando usernames por lote: {e}")
            continue
        for u in users:
            email = _normalizar_correo(u.get("email", ""))
            if email:
                seed_emails.add(email)

    all_courses = await moodle.obtener_cursos()
    siau_courses = [c for c in all_courses if SIAUGESMAT_RE.match(c.get("shortname", ""))]

    sem = asyncio.Semaphore(5)

    async def recopilar_matriculados(course):
        async with sem:
            try:
                users = await moodle.obtener_todos_usuarios_matriculados(int(course["id"]))
            except Exception as e:
                logger.warning(
                    f"Error obteniendo matriculados del curso {course.get('shortname')}: {e}"
                )
                return
            for u in users:
                email = _normalizar_correo(u.get("email", ""))
                if email:
                    seed_emails.add(email)

    batch_size = 5
    for i in range(0, len(siau_courses), batch_size):
        batch = siau_courses[i : i + batch_size]
        await asyncio.gather(*[recopilar_matriculados(c) for c in batch])

    all_users: list[dict] = []
    seed_list = sorted(seed_emails)
    for i in range(0, len(seed_list), 100):
        batch = seed_list[i : i + 100]
        try:
            users = await moodle.obtener_usuarios("email", batch)
        except Exception as e:
            logger.warning(f"Error consultando correos por lote: {e}")
            continue
        all_users.extend(users)

    by_email = _agrupar_usuarios_por_correo(all_users)
    return _construir_filas_correos_duplicados(by_email)


def _requiere_respaldo_docentes(lista: list[dict]) -> bool:
    return bool(lista) and not any(u.get("roles") for u in lista if isinstance(u, dict))


def _extraer_claves_docentes(teachers: object) -> set[str]:
    if not isinstance(teachers, list):
        return set()
    claves = {
        str(t.get("id") or t.get("username") or "").strip().lower()
        for t in teachers
        if isinstance(t, dict)
    }
    claves.discard("")
    return claves


async def _consultar_matriculados_curso_observatorio(
    moodle: ServicioMoodle,
    sem: asyncio.Semaphore,
    course: dict,
    matriculados_por_curso: dict[int, list[dict]],
    docentes_por_curso: dict[int, set[str]],
) -> None:
    async with sem:
        cid = int(course["id"])
        try:
            enrolled = await moodle.obtener_todos_usuarios_matriculados(cid)
        except Exception as e:
            logger.warning(
                f"Error obteniendo matriculados del curso {course.get('shortname')}: {e}"
            )
            return
        lista = enrolled if isinstance(enrolled, list) else []
        matriculados_por_curso[cid] = lista
        if _requiere_respaldo_docentes(lista):
            try:
                teachers = await moodle.obtener_docentes_matriculados_con_acceso(cid)
                claves = _extraer_claves_docentes(teachers)
                if claves:
                    docentes_por_curso[cid] = claves
            except Exception as e:
                logger.warning(
                    f"Error obteniendo docentes de respaldo en {course.get('shortname')}: {e}"
                )


async def _consultar_observatorio(moodle: ServicioMoodle) -> dict[str, object]:
    """Consulta categorías, cursos visibles bajo IDEAD y sus matriculados para el Observatorio."""
    raw_cats = await moodle.obtener_categorias()
    categorias_list = raw_cats if isinstance(raw_cats, list) else []
    ids_idead = obtener_ids_subarbol_idead(categorias_list) if categorias_list else set()
    if not ids_idead:
        logger.warning("Categoría raíz IDEAD no encontrada en Moodle; censo vacío")
        return construir_censo_observatorio(
            cursos=[],
            categorias=[],
            matriculados_por_curso={},
            actualizado_en=datetime.now(UTC).isoformat(),
        )

    all_courses = await moodle.obtener_cursos()
    siau_courses = [
        c
        for c in all_courses
        if int(c.get("visible", 1)) != 0
        and SIAUGESMAT_RE.match(c.get("shortname", ""))
        and int(c.get("categoryid") or c.get("category") or 0) in ids_idead
    ]

    sem = asyncio.Semaphore(5)
    matriculados_por_curso: dict[int, list[dict]] = {}
    docentes_por_curso: dict[int, set[str]] = {}

    batch_size = 5
    for i in range(0, len(siau_courses), batch_size):
        batch = siau_courses[i : i + batch_size]
        await asyncio.gather(
            *[
                _consultar_matriculados_curso_observatorio(
                    moodle, sem, c, matriculados_por_curso, docentes_por_curso
                )
                for c in batch
            ]
        )

    return construir_censo_observatorio(
        cursos=siau_courses,
        categorias=categorias_list,
        matriculados_por_curso=matriculados_por_curso,
        docentes_por_curso=docentes_por_curso,
        actualizado_en=datetime.now(UTC).isoformat(),
    )


async def _consultar_cursos(moodle: ServicioMoodle, params: dict) -> list[dict]:
    search = params.get("search")
    status_filter = params.get("status", "all")
    raw = await moodle.obtener_cursos()
    if search:
        q = search.strip().lower()
        raw = [c for c in raw if q in (c.get("shortname") or "").lower()]
    pattern = params.get("pattern", "all")
    if pattern == "6segments":
        raw = [c for c in raw if (c.get("shortname") or "").count("_") == 5]
    elif pattern == "5segments":
        raw = [c for c in raw if (c.get("shortname") or "").count("_") == 4]
    if status_filter == "orphan":
        raw = await _filtrar_cursos_huerfanos(moodle, raw)
    return raw


async def _consultar_categorias(moodle: ServicioMoodle, params: dict) -> list[dict]:
    return await moodle.obtener_categorias(idnumber=params.get("search"))


async def _consultar_usuarios(moodle: ServicioMoodle, params: dict) -> list[dict]:
    search = params.get("search")
    raw = await moodle.buscar_usuarios(search) if search else []
    if params.get("status") == "never_logged_in":
        raw = [u for u in raw if u.get("lastlogin", 1) == 0]
    return raw


async def _consultar_docentes_inactivos(moodle: ServicioMoodle, params: dict) -> list[dict]:
    cutoff = _parsear_corte(params, allow_semester=False)
    raw_cats = await moodle.obtener_categorias()
    categorias_list = raw_cats if isinstance(raw_cats, list) else []
    ids_idead = obtener_ids_subarbol_idead(categorias_list) if categorias_list else set()

    all_courses = await moodle.obtener_cursos()
    siau_courses = [
        c
        for c in all_courses
        if int(c.get("visible", 1)) != 0
        and SIAUGESMAT_RE.match(c.get("shortname", ""))
        and (not ids_idead or int(c.get("categoryid") or c.get("category") or 0) in ids_idead)
    ]

    sem = asyncio.Semaphore(5)
    results: list[dict] = []

    async def procesar_curso(course):
        async with sem:
            course_id = int(course["id"])
            try:
                teachers = await moodle.obtener_docentes_matriculados_con_acceso(course_id)
            except Exception as e:
                logger.warning(
                    f"Error obteniendo profesores del curso {course.get('shortname')}: {e}"
                )
                return
            results.extend(
                _construir_filas_inactivos(teachers, course, cutoff, categorias=categorias_list)
            )

    batch_size = 5
    for i in range(0, len(siau_courses), batch_size):
        batch = siau_courses[i : i + batch_size]
        await asyncio.gather(*[procesar_curso(c) for c in batch])

    return results


async def _consultar_cursos_inactivos(moodle: ServicioMoodle, params: dict) -> list[dict]:
    cutoff = _parsear_corte(params)
    now = int(time.time())
    all_courses = await moodle.obtener_cursos()
    siau_courses = [c for c in all_courses if SIAUGESMAT_RE.match(c.get("shortname", ""))]

    results = []
    for course in siau_courses:
        last_modified = int(course.get("timemodified", 0) or 0)
        if not last_modified or last_modified >= cutoff:
            continue
        sn = course.get("shortname", "")
        parsed = parsear_shortname(sn)
        program = parsed["cod_prog"] if parsed else ""
        cat_prefix = parsed["cat_prefix"] if parsed else ""
        results.append(
            {
                "id": course.get("id", ""),
                "shortname": sn,
                "fullname": course.get("fullname", ""),
                "categoryname": course.get("categoryname", ""),
                "program": program,
                "cat_prefix": cat_prefix,
                "cat": CAT_NAMES.get(cat_prefix, cat_prefix) if cat_prefix else "",
                "timecreated": course.get("timecreated", ""),
                "timemodified": last_modified,
                "days_since_modified": (now - last_modified) // 86400,
            }
        )
    return results


MANEJADORES_CONSULTA = {
    "courses": _consultar_cursos,
    "categories": _consultar_categorias,
    "users": _consultar_usuarios,
    "duplicate_emails": lambda moodle, _params: _consultar_correos_duplicados(moodle),
    "observatorio": lambda moodle, _params: _consultar_observatorio(moodle),
    "inactive_teachers": _consultar_docentes_inactivos,
    "inactive_courses": _consultar_cursos_inactivos,
}


async def _ejecutar_consulta(moodle: ServicioMoodle, qr):
    manejador = MANEJADORES_CONSULTA.get(qr.entidad)
    if not manejador:
        raise ValueError(f"Entidad desconocida: {qr.entidad}")
    return await manejador(moodle, qr.parametros or {})


@celery_app.task(
    name="app.workers.query_tasks.execute_query",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    time_limit=3600,
    soft_time_limit=3540,
)
def ejecutar_consulta(self, task_id: str):
    db = SessionLocal()
    qr = None
    try:
        marcar_consulta_en_ejecucion(db, task_id)
        qr = obtener_consulta(db, task_id)
        if not qr:
            logger.error(f"QueryResult {task_id} no encontrado")
            return

        moodle = obtener_servicio_moodle(qr.modalidad)

        raw = ejecutar_moodle_async(moodle, _ejecutar_consulta(moodle, qr))
        conteo = int(raw.get("total_students", 0)) if isinstance(raw, dict) else len(raw)

        marcar_consulta_completada(db, task_id, raw, conteo)

    except Exception as exc:
        logger.exception(f"Fallo en query {task_id}")
        marcar_consulta_fallida(db, task_id, str(exc))
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc

    finally:
        db.close()
