"""Umbrales por defecto del comparador de cursos (valores puros).

En producción, el worker de la FASE 2 inyecta los valores reales de
app.core.config.Settings (COURSE_MAX_AGE_SECONDS / COURSE_DISAPPEARED_AGE_SECONDS).
Estas constantes son el fallback para el uso del núcleo puro y los tests.
"""

EDAD_MAXIMA_CURSO_SEGUNDOS: int = 24 * 30 * 24 * 3600  # 24 meses
EDAD_DESAPARICION_CURSO_SEGUNDOS: int = 18 * 30 * 24 * 3600  # 18 meses
