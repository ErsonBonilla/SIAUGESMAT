"""Índice base de cursos SIAUGESMAT — transformaciones puras.

Helpers compartidos para indexar cursos por su shortname parseado.
Sin I/O: operan solo sobre dicts recibidos por parámetro.
"""

from app.pipeline.nombres_cortos import parsear_shortname


def construir_clave_base(parsed: dict) -> tuple[str, ...]:
    return (
        parsed["cat_prefix"],
        parsed["cod_prog"],
        parsed["semestre"],
        parsed["cod_curso"],
        parsed["grupo"],
    )


def construir_cadena_clave_base(parsed: dict) -> str:
    return f"{parsed['cat_prefix']}_{parsed['cod_prog']}_s{parsed['semestre']}_{parsed['cod_curso']}_G-{parsed['grupo']}"


def indexar_cursos(courses: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parsear_shortname(sn)
        if not parsed:
            continue
        bk = construir_cadena_clave_base(parsed)
        c["_parsed"] = parsed
        c["_base_key"] = bk
        index.setdefault(bk, []).append(c)
    return index


def construir_mapa_matriculaciones(enrolments: list[dict]) -> dict[str, str]:
    return {
        e["course_shortname"]: e.get("username", "")
        for e in enrolments
        if e.get("course_shortname")
    }
