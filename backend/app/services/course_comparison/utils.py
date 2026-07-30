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
