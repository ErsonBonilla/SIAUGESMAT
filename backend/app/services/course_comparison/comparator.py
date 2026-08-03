"""Shim de compatibilidad: re-exporta CourseComparisonService desde el núcleo puro."""
from app.pipeline.course_comparison.comparator import CourseComparisonService

__all__ = ["CourseComparisonService"]
