from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.parsers.patterns import parse_shortname


def parse_sn(shortname: str) -> Optional[Dict[str, str]]:
    return parse_shortname(shortname)


def get_suffix(shortname: str) -> str:
    parsed = parse_shortname(shortname)
    if not parsed:
        return ""
    return parsed["suffix"] or ""


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


def get_course_professor(course: Dict) -> Optional[str]:
    custom = course.get("customfields", [])
    for field in custom:
        if field.get("shortname") == "professor":
            return field.get("value")
    return None


def get_course_age_seconds(course: Dict) -> int:
    created = course.get("timecreated", 0)
    if not created:
        created = course.get("startdate", 0)
    return int(datetime.now(timezone.utc).timestamp()) - created


def is_course_hidden(course: Dict) -> bool:
    return course.get("visible", 1) == 0


def first_visible(candidates: List[Dict]) -> Dict:
    for c in candidates:
        if c.get("visible", 1) == 1:
            return c
    return candidates[0]
