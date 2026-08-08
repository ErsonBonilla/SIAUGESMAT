"""Shim de compatibilidad: re-exporta el comparador de cursos (FASE 2).

La implementación vive en el núcleo puro app.pipeline.course_comparison.
Este paquete se mantiene como puente para los workers y tests existentes.
"""

from app.pipeline.course_comparison import CourseComparisonService
from app.services.parsers.patterns import SIAUGESMAT_PATTERN

__all__ = ["SIAUGESMAT_PATTERN", "CourseComparisonService"]
