"""Comparador de cursos (FASE 2) — núcleo puro.

Contiene la lógica de comparación entre los cursos existentes en Moodle y la
nueva carga académica, sin tocar base de datos ni settings: los umbrales de
edad se inyectan por parámetro (ver app.workers.phases.fase2_analisis).
"""

from app.pipeline.comparacion_cursos.comparador import ServicioComparacionCursos

__all__ = ["ServicioComparacionCursos"]
