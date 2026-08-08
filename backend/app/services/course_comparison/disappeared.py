"""Shim de compatibilidad: re-exporta disappeared de course_comparison desde el núcleo puro."""

from app.pipeline.course_comparison.disappeared import find_disappeared_courses

__all__ = ["find_disappeared_courses"]
