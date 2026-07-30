import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Execution
from app.repositories.execution_repo import (
    create_execution,
    mark_completed,
    mark_running,
    set_report_dir,
)
from app.repositories.log_repo import save_log
from app.services.etl import ETLService
from app.services.moodle_factory import get_moodle_service
from app.services.parsers.patterns import parse_shortname
from app.services.reports import ReportService

logger = logging.getLogger(__name__)


def _build_base_key(parsed: Dict[str, str]) -> str:
    return f"{parsed['cat_prefix']}_{parsed['cod_prog']}_s{parsed['semestre']}_{parsed['cod_curso']}_G-{parsed['grupo']}"


def _index_courses(courses: List[Dict]) -> Dict[str, List[Dict]]:
    index: Dict[str, List[Dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parse_shortname(sn)
        if not parsed:
            continue
        bk = _build_base_key(parsed)
        c["_parsed"] = parsed
        c["_base_key"] = bk
        index.setdefault(bk, []).append(c)
    return index


def _build_enrolment_map(enrolments: List[Dict]) -> Dict[str, str]:
    return {e["course_shortname"]: e.get("username", "") for e in enrolments if e.get("course_shortname")}


def _build_user_map(users: List[Dict]) -> Dict[str, Dict]:
    return {u.get("cedula", ""): u for u in users if u.get("cedula")}


async def detect(
    db: Session,
    semester: str,
    modalidad: str,
    new_file_path: str,
) -> Tuple[Dict[str, Any], Optional[str]]:
    new_data = ETLService.process(new_file_path, modalidad)
    new_courses = new_data.get("courses", [])
    new_enrolments = new_data.get("enrolments", [])
    new_users = new_data.get("users", [])

    if not new_courses:
        return {}, "El archivo nuevo no contiene cursos."

    previous = (
        db.query(Execution)
        .filter(
            Execution.semester == semester,
            Execution.modalidad == modalidad,
            Execution.status == "completed",
        )
        .order_by(Execution.created_at.desc())
        .first()
    )
    if not previous:
        return {}, f"No se encontró una ejecución previa completada para el semestre {semester}."

    old_file_path = os.path.join(settings.UPLOAD_DIR, previous.filename)
    if not os.path.exists(old_file_path):
        return {}, f"El archivo de la ejecución anterior ({previous.filename}) ya no existe en el servidor."

    old_data = ETLService.process(old_file_path, modalidad)
    old_courses = old_data.get("courses", [])

    old_index = _index_courses(old_courses)
    new_index = _index_courses(new_courses)

    enrolment_map_old = _build_enrolment_map(old_data.get("enrolments", []))
    enrolment_map_new = _build_enrolment_map(new_enrolments)
    user_map_new = _build_user_map(new_users)

    common_keys = set(old_index.keys()) & set(new_index.keys())

    moodle_service = get_moodle_service(modalidad)

    novedades: List[Dict] = []
    for bk in common_keys:
        old_course = old_index[bk][0]
        new_course = new_index[bk][0]

        old_suffix = (old_course["_parsed"].get("suffix") or "").strip()
        new_suffix = (new_course["_parsed"].get("suffix") or "").strip()

        if old_suffix == new_suffix:
            continue

        old_sn = old_course["shortname"]
        new_sn = new_course["shortname"]

        old_username = _find_username_for_course(old_sn, enrolment_map_old, old_data.get("users", []))
        new_username = _find_username_for_course(new_sn, enrolment_map_new, new_users)

        old_prof_name = _resolve_prof_name(old_username, old_data.get("users", []))
        new_prof_user = user_map_new.get(new_suffix, {})
        new_prof_name = new_prof_user.get("firstname", "") + " " + new_prof_user.get("lastname", "")
        new_prof_name = new_prof_name.strip() or new_username

        expected_new_sn = f"{bk}_{new_suffix}" if new_suffix else bk

        action = "hide_and_create"
        target_course_id = None

        try:
            existing_courses = await moodle_service.get_courses(shortname=expected_new_sn)
            if existing_courses:
                course = existing_courses[0]
                if course.get("visible", 1) == 0:
                    action = "unhide"
                    target_course_id = int(course["id"])
        except Exception as e:
            logger.warning(f"Error consultando Moodle para {expected_new_sn}: {e}")

        novedades.append({
            "id": f"nov_{bk}",
            "base_key": bk,
            "old_shortname": old_sn,
            "new_shortname": new_sn,
            "old_prof_cedula": old_suffix or None,
            "new_prof_cedula": new_suffix or None,
            "old_prof_name": old_prof_name,
            "new_prof_name": new_prof_name,
            "course_fullname": new_course.get("fullname", ""),
            "action": action,
            "target_course_id": target_course_id,
        })

    return {
        "semester": semester,
        "previous_execution_id": previous.id,
        "previous_filename": previous.filename,
        "total_compared": len(common_keys),
        "novedades": novedades,
    }, None


def _find_username_for_course(shortname: str, enrolment_map: Dict[str, str], users: List[Dict]) -> str:
    username = enrolment_map.get(shortname, "")
    return username


def _resolve_prof_name(username: str, users: List[Dict]) -> str:
    if not username:
        return ""
    for u in users:
        if u.get("username") == username:
            first = u.get("firstname", "")
            last = u.get("lastname", "")
            return f"{first} {last}".strip()
    return username


async def apply(
    db: Session,
    semester: str,
    modalidad: str,
    items: List[Dict],
    filename: str = "novedades.xlsx",
) -> Dict[str, Any]:
    moodle_config = settings.get_moodle_config(modalidad)
    execution = create_execution(db, filename, semester, "both", modalidad, moodle_config["version"])
    execution_id = execution.id
    execution = mark_running(db, execution_id)
    moodle_service = get_moodle_service(modalidad)
    started_at = datetime.now(timezone.utc)

    results: List[Dict] = []
    applied = 0
    failed = 0

    for item in items:
        nov_id = item["id"]
        action = item["action"]
        item["execution_id"] = execution_id
        try:
            if action == "hide_and_create":
                result = await _apply_hide_and_create(moodle_service, item, db)
            elif action == "unhide":
                result = await _apply_unhide(moodle_service, item, db)
            else:
                result = {"success": False, "message": f"Acción desconocida: {action}"}

            if result["success"]:
                applied += 1
            else:
                failed += 1
        except Exception as e:
            logger.exception(f"Error aplicando novedad {nov_id}")
            result = {"success": False, "message": str(e)}
            failed += 1

        results.append({
            "novedad_id": nov_id,
            "success": result["success"],
            "action": action,
            "message": result.get("message", ""),
        })

    duration = (datetime.now(timezone.utc) - started_at).total_seconds()
    metrics = {
        "novedades_detectadas": len(items),
        "novedades_aplicadas": applied,
        "novedades_fallidas": failed,
    }
    mark_completed(db, execution_id, metrics, failed, duration)

    # Generar reportes si hay resultados
    try:
        report_dir = ReportService.generate_all(execution_id, db)
        set_report_dir(db, execution_id, report_dir)
    except Exception:
        logger.exception("Error generando reportes de novedades")

    return {
        "total": len(items),
        "applied": applied,
        "failed": failed,
        "results": results,
    }


async def _apply_hide_and_create(
    moodle_service,
    item: Dict,
    db: Session = None,
) -> Dict[str, Any]:
    old_sn = item["old_shortname"]
    new_sn = item["new_shortname"]
    fullname = item.get("course_fullname", new_sn)
    category_idnumber = item.get("category_idnumber", "")

    hide_ok = True
    try:
        existing_old = await moodle_service.get_courses(shortname=old_sn)
        if existing_old:
            old_course_id = int(existing_old[0]["id"])
            await moodle_service.update_courses([{"id": old_course_id, "visible": 0}])
            logger.info(f"Curso ocultado: {old_sn}")
    except Exception as e:
        logger.warning(f"Error al ocultar curso {old_sn}: {e}")
        hide_ok = False

    create_ok = True
    try:
        existing_new = await moodle_service.get_courses(shortname=new_sn)
        if not existing_new:
            course_data = {
                "shortname": new_sn,
                "fullname": fullname,
                "categoryidnumber": category_idnumber,
                "format": settings.DEFAULT_COURSE_FORMAT,
                "visible": 1,
            }
            await moodle_service.create_courses([course_data])
            logger.info(f"Curso creado: {new_sn}")
        else:
            logger.info(f"Curso {new_sn} ya existe, se omite creación")
    except Exception as e:
        logger.error(f"Error al crear curso {new_sn}: {e}")
        create_ok = False

    enrol_ok = True
    new_prof_username = item.get("new_prof_username", "")
    if new_prof_username and create_ok:
        try:
            created = await moodle_service.get_courses(shortname=new_sn)
            if created:
                course_id = int(created[0]["id"])
                enrol_result = await moodle_service.enrol_users([{
                    "username": new_prof_username,
                    "course_shortname": new_sn,
                    "role": "editingteacher",
                }])
                if isinstance(enrol_result, dict) and not enrol_result.get("success", True):
                    enrol_ok = False
                    logger.warning(f"Error matriculando {new_prof_username} en {new_sn}: {enrol_result.get('errors')}")
                else:
                    logger.info(f"Profesor {new_prof_username} matriculado en {new_sn}")
        except Exception as e:
            logger.error(f"Error matriculando profesor {new_prof_username} en {new_sn}: {e}")
            enrol_ok = False

    execution_id = item.get("execution_id")
    if execution_id and db:
        if hide_ok:
            save_log(db, execution_id, "4", "course_hidden",
                     old_sn, {"fullname": fullname, "reason": "novedad_profesor"})
        if create_ok:
            save_log(db, execution_id, "4", "course_created",
                     new_sn, {"fullname": fullname, "category_idnumber": category_idnumber,
                              "reason": "novedad_profesor"})
        if enrol_ok and new_prof_username:
            save_log(db, execution_id, "4", "enrolment_ok",
                     new_prof_username, {"course": new_sn, "fullname": fullname})

    success = hide_ok and create_ok
    msg_parts = []
    if hide_ok:
        msg_parts.append(f"Curso {old_sn} ocultado")
    else:
        msg_parts.append(f"No se pudo ocultar {old_sn}")
    if create_ok:
        msg_parts.append(f"curso {new_sn} creado")
    else:
        msg_parts.append(f"no se pudo crear {new_sn}")
    if enrol_ok:
        msg_parts.append(f"profesor matriculado")
    else:
        msg_parts.append(f"error en matriculación")

    return {"success": success, "message": "; ".join(msg_parts)}


async def _apply_unhide(
    moodle_service,
    item: Dict,
    db: Session = None,
) -> Dict[str, Any]:
    course_id = item.get("target_course_id")
    shortname = item.get("new_shortname", "")

    if not course_id and shortname:
        try:
            existing = await moodle_service.get_courses(shortname=shortname)
            if existing:
                course_id = int(existing[0]["id"])
        except Exception as e:
            return {"success": False, "message": f"Error buscando curso {shortname}: {e}"}

    if not course_id:
        return {"success": False, "message": f"No se encontró el curso para rehabilitar"}

    try:
        await moodle_service.update_courses([{"id": course_id, "visible": 1}])
        logger.info(f"Curso rehabilitado: {shortname} (id={course_id})")
    except Exception as e:
        return {"success": False, "message": f"Error al rehabilitar curso {shortname}: {e}"}

    new_prof_username = item.get("new_prof_username", "")
    if new_prof_username:
        try:
            enrol_result = await moodle_service.enrol_users([{
                "username": new_prof_username,
                "course_shortname": shortname,
                "role": "editingteacher",
            }])
            if isinstance(enrol_result, dict) and not enrol_result.get("success", True):
                logger.warning(f"Error matriculando {new_prof_username} en {shortname}: {enrol_result.get('errors')}")
            else:
                logger.info(f"Profesor {new_prof_username} matriculado en {shortname}")
        except Exception as e:
            logger.warning(f"Error matriculando profesor en {shortname}: {e}")

    execution_id = item.get("execution_id")
    if execution_id and db:
        save_log(db, execution_id, "4", "course_activated",
                 shortname, {"fullname": item.get("course_fullname", ""), "reason": "novedad_profesor"})
        if new_prof_username:
            save_log(db, execution_id, "4", "enrolment_ok",
                     new_prof_username, {"course": shortname, "fullname": item.get("course_fullname", "")})

    return {"success": True, "message": f"Curso {shortname} rehabilitado y profesor matriculado"}
