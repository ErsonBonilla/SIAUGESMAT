"""Índice base de cursos SIAUGESMAT — transformaciones puras.

Helpers compartidos para indexar cursos por su shortname parseado.
Sin I/O: operan solo sobre dicts recibidos por parámetro.
"""
from typing import Dict, List, Tuple

from app.services.parsers.patterns import parse_shortname


def build_base_key(parsed: Dict) -> Tuple[str, ...]:
    return (
        parsed["cat_prefix"],
        parsed["cod_prog"],
        parsed["semestre"],
        parsed["cod_curso"],
        parsed["grupo"],
    )


def build_base_key_str(parsed: Dict) -> str:
    return f"{parsed['cat_prefix']}_{parsed['cod_prog']}_s{parsed['semestre']}_{parsed['cod_curso']}_G-{parsed['grupo']}"


def index_courses(courses: List[Dict]) -> Dict[str, List[Dict]]:
    index: Dict[str, List[Dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parse_shortname(sn)
        if not parsed:
            continue
        bk = build_base_key_str(parsed)
        c["_parsed"] = parsed
        c["_base_key"] = bk
        index.setdefault(bk, []).append(c)
    return index


def build_enrolment_map(enrolments: List[Dict]) -> Dict[str, str]:
    return {e["course_shortname"]: e.get("username", "") for e in enrolments if e.get("course_shortname")}
