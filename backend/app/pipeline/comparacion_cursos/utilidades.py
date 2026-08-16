from datetime import UTC, datetime

from app.pipeline.indice_cursos import (
    construir_cadena_clave_base,
    construir_clave_base,
    construir_mapa_matriculaciones,
    indexar_cursos,
)
from app.pipeline.nombres_cortos import parsear_shortname

__all__ = [
    "construir_cadena_clave_base",
    "construir_clave_base",
    "construir_mapa_matriculaciones",
    "es_curso_oculto",
    "indexar_cursos",
    "obtener_edad_curso_segundos",
    "obtener_profesor_curso",
    "obtener_sufijo",
    "primer_visible",
]


def obtener_sufijo(shortname: str) -> str:
    parsed = parsear_shortname(shortname)
    if not parsed:
        return ""
    return parsed["suffix"] or ""


def obtener_profesor_curso(course: dict) -> str | None:
    custom = course.get("customfields", [])
    for field in custom:
        if field.get("shortname") == "professor":
            return field.get("value")
    return None


def obtener_edad_curso_segundos(course: dict) -> int:
    created = course.get("timecreated", 0)
    if not created:
        created = course.get("startdate", 0)
    return int(datetime.now(UTC).timestamp()) - created


def es_curso_oculto(course: dict) -> bool:
    return course.get("visible", 1) == 0


def primer_visible(candidates: list[dict]) -> dict:
    for c in candidates:
        if c.get("visible", 1) == 1:
            return c
    return candidates[0]
