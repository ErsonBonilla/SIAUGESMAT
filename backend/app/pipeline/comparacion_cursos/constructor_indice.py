from app.pipeline.comparacion_cursos.utilidades import construir_clave_base
from app.pipeline.nombres_cortos import parsear_shortname


def construir_indice_shortnames(courses: list[dict]) -> dict[str, dict]:
    return {c.get("shortname", ""): c for c in courses if c.get("shortname")}


def construir_indice_claves_base(courses: list[dict]) -> dict[tuple[str, ...], list[dict]]:
    index: dict[tuple[str, ...], list[dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parsear_shortname(sn)
        if parsed:
            key = construir_clave_base(parsed)
            index.setdefault(key, []).append(c)
    return index


def construir_indice_nucleo(courses: list[dict]) -> dict[tuple[str, ...], list[dict]]:
    index: dict[tuple[str, ...], list[dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parsear_shortname(sn)
        if parsed:
            key = (parsed["cod_prog"], parsed["cod_curso"], parsed["semestre"])
            index.setdefault(key, []).append(c)
    return index
