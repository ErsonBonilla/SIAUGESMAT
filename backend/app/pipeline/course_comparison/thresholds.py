"""Umbrales por defecto del comparador de cursos (valores puros).

En producción, el worker de la FASE 2 inyecta los valores reales de
app.core.config.Settings (COURSE_MAX_AGE_SECONDS / COURSE_DISAPPEARED_AGE_SECONDS).
Estas constantes son el fallback para el uso del núcleo puro y los tests.
"""

DEFAULT_COURSE_MAX_AGE_SECONDS: int = 24 * 30 * 24 * 3600  # 24 meses
DEFAULT_COURSE_DISAPPEARED_AGE_SECONDS: int = 18 * 30 * 24 * 3600  # 18 meses
