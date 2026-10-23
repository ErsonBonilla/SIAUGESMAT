"""Umbrales por defecto del comparador de cursos (valores puros).

En producción, el worker de la FASE 2 inyecta el valor real de
app.core.config.Settings (COURSE_MAX_AGE_SECONDS).
Esta constante es el fallback para el uso del núcleo puro y los tests.
"""

EDAD_MAXIMA_CURSO_SEGUNDOS: int = (24 * 30 + 1) * 24 * 3600  # 24 meses y 1 día
