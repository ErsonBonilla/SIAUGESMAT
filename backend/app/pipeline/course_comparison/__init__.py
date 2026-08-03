"""Comparador de cursos (FASE 2) — núcleo puro.

Contiene la lógica de comparación entre los cursos existentes en Moodle y la
nueva carga académica, sin tocar base de datos ni settings: los umbrales de
edad se inyectan por parámetro (ver app.workers.phases.phase2_analyze).
"""
from app.pipeline.course_comparison.comparator import CourseComparisonService

__all__ = ["CourseComparisonService"]
