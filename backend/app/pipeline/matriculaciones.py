"""Transformaciones sobre matrículas y validación de docentes en cursos (FASE 2) — puras."""

from app.pipeline.nombres_cortos import parsear_shortname

Enrolment = dict[str, object]
User = dict[str, object]


def _texto_campo(mapa: dict[str, object], clave: str) -> str:
    val = mapa.get(clave)
    return str(val) if val is not None and val != "" else ""


def resolver_matriculaciones(
    enrolments: list[Enrolment],
    username_map: dict[str, str],
) -> list[Enrolment]:
    """Reemplaza el username ETL por el username Moodle resuelto.

    Los usuarios sin resolución conservan su username ETL original.
    """
    resolved: list[Enrolment] = []
    for enr in enrolments:
        uname = _texto_campo(enr, "username")
        resolved_username = username_map.get(uname, uname)
        resolved.append({**enr, "username": resolved_username})
    return resolved


def _construir_incidencia_docente(
    sn: str,
    etl_uname: str,
    users_by_uname: dict[str, User],
    courses_by_sn: dict[str, dict],
) -> dict[str, str]:
    u = users_by_uname.get(etl_uname, {})
    c = courses_by_sn.get(sn, {})
    parsed = parsear_shortname(sn) or {}
    return {
        "email": _texto_campo(u, "email"),
        "username": etl_uname,
        "shortname": sn,
        "fullname": _texto_campo(c, "fullname"),
        "firstname": _texto_campo(u, "firstname"),
        "lastname": _texto_campo(u, "lastname"),
        "cat": _texto_campo(parsed, "cat_prefix"),
        "programa": _texto_campo(parsed, "cod_prog"),
        "semestre": _texto_campo(parsed, "semestre"),
        "grupo": _texto_campo(parsed, "grupo"),
    }


def _registrar_incidencia_unica(
    sn: str,
    etl_uname: str,
    vistos: set[tuple[str, str]],
    incidencias: list[dict[str, str]],
    users_by_uname: dict[str, User],
    courses_by_sn: dict[str, dict],
) -> None:
    clave = (sn, etl_uname)
    if clave in vistos:
        return
    vistos.add(clave)
    incidencias.append(_construir_incidencia_docente(sn, etl_uname, users_by_uname, courses_by_sn))


def _filtrar_lote_cursos(
    items: list[dict],
    enrols_by_course: dict[str, list[str]],
    username_map: dict[str, str],
    cursos_bloqueados: set[str],
    vistos: set[tuple[str, str]],
    incidencias: list[dict[str, str]],
    users_by_uname: dict[str, User],
    courses_by_sn: dict[str, dict],
) -> list[dict]:
    filtrados: list[dict] = []
    for item in items:
        sn = _texto_campo(item, "shortname")
        faltantes = [u for u in enrols_by_course.get(sn, []) if u not in username_map]
        if faltantes:
            cursos_bloqueados.add(sn)
            for etl_uname in faltantes:
                _registrar_incidencia_unica(
                    sn, etl_uname, vistos, incidencias, users_by_uname, courses_by_sn
                )
            continue
        filtrados.append(item)
    return filtrados


def _agrupar_matriculas_por_curso(enrolments: list[Enrolment]) -> dict[str, list[str]]:
    enrols_by_course: dict[str, list[str]] = {}
    for e in enrolments:
        sn = _texto_campo(e, "course_shortname")
        uname = _texto_campo(e, "username")
        if sn and uname:
            enrols_by_course.setdefault(sn, []).append(uname)
    return enrols_by_course


def filtrar_cursos_y_matriculas_sin_docente(
    to_create: list[dict],
    enrolments: list[Enrolment],
    etl_users: list[User],
    etl_courses: list[dict],
    username_map: dict[str, str],
    *,
    to_update: list[dict] | None = None,
    to_activate: list[dict] | None = None,
) -> tuple[list[dict], list[Enrolment], list[dict[str, str]]]:
    """Omite la creación/actualización de cursos y matrículas cuyos docentes no existen en Moodle."""
    users_by_uname: dict[str, User] = {
        str(u["username"]): u for u in etl_users if u.get("username")
    }
    courses_by_sn: dict[str, dict] = {
        str(c["shortname"]): c for c in etl_courses if c.get("shortname")
    }
    enrols_by_course = _agrupar_matriculas_por_curso(enrolments)

    cursos_bloqueados: set[str] = set()
    incidencias: list[dict[str, str]] = []
    vistos: set[tuple[str, str]] = set()

    args_filtro = (
        enrols_by_course,
        username_map,
        cursos_bloqueados,
        vistos,
        incidencias,
        users_by_uname,
        courses_by_sn,
    )
    cursos_filtrados = _filtrar_lote_cursos(to_create, *args_filtro)
    if to_update is not None:
        to_update[:] = _filtrar_lote_cursos(list(to_update), *args_filtro)
    if to_activate is not None:
        to_activate[:] = _filtrar_lote_cursos(list(to_activate), *args_filtro)

    matriculas_filtradas: list[Enrolment] = []
    for enr in enrolments:
        sn = _texto_campo(enr, "course_shortname")
        etl_uname = _texto_campo(enr, "username")
        if etl_uname not in username_map or sn in cursos_bloqueados:
            if etl_uname and etl_uname not in username_map:
                _registrar_incidencia_unica(
                    sn, etl_uname, vistos, incidencias, users_by_uname, courses_by_sn
                )
            continue
        matriculas_filtradas.append({**enr, "username": username_map[etl_uname]})

    return cursos_filtrados, matriculas_filtradas, incidencias
