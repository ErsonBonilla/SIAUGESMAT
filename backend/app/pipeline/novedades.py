"""Detección de novedades entre dos cargas ETL — transformaciones puras.

Compara el estado anterior y el nuevo de cursos/docentes y emite las
novedades (cambio de profesor, curso eliminado, curso nuevo) sin tocar
la base de datos ni el filesystem.
"""
from typing import Any, Dict, List, Tuple

from app.pipeline.course_index import build_enrolment_map, index_courses

Novedad = Dict[str, Any]


def _build_user_map(users: List[Dict]) -> Dict[str, Dict]:
    return {u.get("cedula", ""): u for u in users if u.get("cedula")}


def _resolve_prof_name(username: str, users: List[Dict]) -> str:
    if not username:
        return ""
    for u in users:
        if u.get("username") == username:
            first = u.get("firstname", "")
            last = u.get("lastname", "")
            return f"{first} {last}".strip()
    return username


def _new_prof_name(new_suffix: str, user_map_new: Dict[str, Dict], username: str) -> str:
    prof_user = user_map_new.get(new_suffix, {})
    full = f"{prof_user.get('firstname', '')} {prof_user.get('lastname', '')}".strip()
    return full or username


def detect_novedades(
    old_data: Dict[str, Any],
    new_data: Dict[str, Any],
) -> Tuple[List[Novedad], Dict[str, int]]:
    """Compara dos cargas ETL y detecta novedades de cursos.

    Retorna (novedades, stats), donde stats incluye ``total_compared``.

    Novedades emitidas:
      - ``cambio_profesor``: el sufijo (cédula del profesor) cambió.
      - ``curso_eliminado``: el curso existía en old pero no en new.
      - ``curso_nuevo``: el curso existe en new pero no en old.
    """
    old_courses = old_data.get("courses", [])
    new_courses = new_data.get("courses", [])
    old_users = old_data.get("users", [])
    new_users = new_data.get("users", [])
    old_enrolments = old_data.get("enrolments", [])
    new_enrolments = new_data.get("enrolments", [])

    old_index = index_courses(old_courses)
    new_index = index_courses(new_courses)

    enrolment_map_old = build_enrolment_map(old_enrolments)
    enrolment_map_new = build_enrolment_map(new_enrolments)
    user_map_new = _build_user_map(new_users)

    common_keys = set(old_index.keys()) & set(new_index.keys())

    novedades: List[Novedad] = []

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

        old_username = enrolment_map_old.get(old_sn, "")
        new_username = enrolment_map_new.get(new_sn, "")

        novedades.append({
            "id": f"nov_{bk}",
            "base_key": bk,
            "old_shortname": old_sn,
            "new_shortname": new_sn,
            "old_prof_cedula": old_suffix or None,
            "new_prof_cedula": new_suffix or None,
            "old_prof_name": _resolve_prof_name(old_username, old_users),
            "new_prof_name": _new_prof_name(new_suffix, user_map_new, new_username),
            "course_fullname": new_course.get("fullname", ""),
            "action": "cambio_profesor",
            "target_course_id": None,
        })

    # Cursos que desaparecieron (en old pero no en new)
    for bk, courses in old_index.items():
        if bk in new_index:
            continue
        old_course = courses[0]
        old_sn = old_course["shortname"]
        old_suffix = (old_course["_parsed"].get("suffix") or "").strip()
        old_username = enrolment_map_old.get(old_sn, "")
        novedades.append({
            "id": f"des_{bk}",
            "base_key": bk,
            "old_shortname": old_sn,
            "new_shortname": "",
            "old_prof_cedula": old_suffix or None,
            "new_prof_cedula": None,
            "old_prof_name": _resolve_prof_name(old_username, old_users),
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
        new_username = enrolment_map_new.get(new_sn, "")
        novedades.append({
            "id": f"new_{bk}",
            "base_key": bk,
            "old_shortname": "",
            "new_shortname": new_sn,
            "old_prof_cedula": None,
            "new_prof_cedula": new_suffix or None,
            "old_prof_name": "",
            "new_prof_name": _new_prof_name(new_suffix, user_map_new, new_username),
            "course_fullname": new_course.get("fullname", ""),
            "action": "curso_nuevo",
            "target_course_id": None,
        })

    stats = {
        "common": len(common_keys),
        "old_courses": len(old_index),
        "new_courses": len(new_index),
        "total_compared": len(common_keys) + len(old_index) + len(new_index),
    }
    return novedades, stats
