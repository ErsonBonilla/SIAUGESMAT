from datetime import UTC, datetime

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
    "first_visible",
    "get_course_age_seconds",
    "get_course_professor",
    "get_suffix",
    "index_courses",
    "is_course_hidden",
]


def get_suffix(shortname: str) -> str:
    parsed = parse_shortname(shortname)
    if not parsed:
        return ""
    return parsed["suffix"] or ""


def get_course_professor(course: dict) -> str | None:
    custom = course.get("customfields", [])
    for field in custom:
        if field.get("shortname") == "professor":
            return field.get("value")
    return None


def get_course_age_seconds(course: dict) -> int:
    created = course.get("timecreated", 0)
    if not created:
        created = course.get("startdate", 0)
    return int(datetime.now(UTC).timestamp()) - created


def is_course_hidden(course: dict) -> bool:
    return course.get("visible", 1) == 0


def first_visible(candidates: list[dict]) -> dict:
    for c in candidates:
        if c.get("visible", 1) == 1:
            return c
    return candidates[0]
