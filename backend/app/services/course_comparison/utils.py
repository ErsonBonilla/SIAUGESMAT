"""Shim de compatibilidad: re-exporta utils de course_comparison desde el núcleo puro."""

from app.pipeline.course_comparison.utils import (
    build_base_key,
    build_base_key_str,
    build_enrolment_map,
    first_visible,
    get_course_age_seconds,
    get_course_professor,
    get_suffix,
    index_courses,
    is_course_hidden,
)

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
