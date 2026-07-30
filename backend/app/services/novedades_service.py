import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Execution
from app.services.etl import ETLService
from app.services.moodle_factory import get_moodle_service
from app.services.parsers.patterns import parse_shortname

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

    # Cambio de profesor en cursos que existen en ambas cargas
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

        action = "cambio_profesor"

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
            "target_course_id": None,
        })

    # Cursos que desaparecieron (en old pero no en new)
    for bk, courses in old_index.items():
        if bk in new_index:
            continue
        old_course = courses[0]
        old_sn = old_course["shortname"]
        old_suffix = (old_course["_parsed"].get("suffix") or "").strip()
        old_username = _find_username_for_course(old_sn, enrolment_map_old, old_data.get("users", []))
        old_prof_name = _resolve_prof_name(old_username, old_data.get("users", []))
        novedades.append({
            "id": f"des_{bk}",
            "base_key": bk,
            "old_shortname": old_sn,
            "new_shortname": "",
            "old_prof_cedula": old_suffix or None,
            "new_prof_cedula": None,
            "old_prof_name": old_prof_name,
            "new_prof_name": "",
            "course_fullname": old_course.get("fullname", ""),
            "action": "curso_eliminado",
            "target_course_id": None,
        })

    # Cursos nuevos (en new pero no en old)
    for bk, courses in new_index.items():
        if bk in old_index:
            continue
        new_course = courses[0]
        new_sn = new_course["shortname"]
        new_suffix = (new_course["_parsed"].get("suffix") or "").strip()
        new_username = _find_username_for_course(new_sn, enrolment_map_new, new_users)
        new_prof_user = user_map_new.get(new_suffix, {})
        new_prof_name = new_prof_user.get("firstname", "") + " " + new_prof_user.get("lastname", "")
        new_prof_name = new_prof_name.strip() or new_username
        novedades.append({
            "id": f"new_{bk}",
            "base_key": bk,
            "old_shortname": "",
            "new_shortname": new_sn,
            "old_prof_cedula": None,
            "new_prof_cedula": new_suffix or None,
            "old_prof_name": "",
            "new_prof_name": new_prof_name,
            "course_fullname": new_course.get("fullname", ""),
            "action": "curso_nuevo",
            "target_course_id": None,
        })

    return {
        "semester": semester,
        "previous_execution_id": previous.id,
        "previous_filename": previous.filename,
        "total_compared": len(common_keys) + len(old_index) + len(new_index),
        "novedades": novedades,
    }, None


def _find_username_for_course(shortname: str, enrolment_map: Dict[str, str], users: List[Dict]) -> str:
    return enrolment_map.get(shortname, "")


def _resolve_prof_name(username: str, users: List[Dict]) -> str:
    if not username:
        return ""
    for u in users:
        if u.get("username") == username:
            first = u.get("firstname", "")
            last = u.get("lastname", "")
            return f"{first} {last}".strip()
    return username
