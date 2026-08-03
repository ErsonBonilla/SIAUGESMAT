from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.pipeline.course_index import (
    build_base_key,
    build_base_key_str,
    build_enrolment_map,
    index_courses,
)
from app.pipeline.shortnames import parse_shortname

__all__ = [
    "build_base_key",
    "build_base_key_str",
    "build_enrolment_map",
    "index_courses",
    "get_suffix",
    "get_course_professor",
    "get_course_age_seconds",
    "is_course_hidden",
    "first_visible",
]


def get_suffix(shortname: str) -> str:
    parsed = parse_shortname(shortname)
    if not parsed:
        return ""
    return parsed["suffix"] or ""


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
