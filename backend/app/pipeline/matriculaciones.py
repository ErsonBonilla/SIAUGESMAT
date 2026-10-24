"""Transformaciones sobre matrículas y validación de docentes en cursos (FASE 2) — puras."""

from app.pipeline.nombres_cortos import parsear_shortname

Enrolment = dict[str, object]
User = dict[str, object]


def resolver_matriculaciones(
    enrolments: list[Enrolment],
    username_map: dict[str, str],
) -> list[Enrolment]:
    """Reemplaza el username ETL por el username Moodle resuelto.

    Los usuarios sin resolución conservan su username ETL original.
    """
    resolved: list[Enrolment] = []
    for enr in enrolments:
        resolved_username = username_map.get(str(enr["username"]), str(enr["username"]))
        resolved.append({**enr, "username": resolved_username})
    return resolved


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
    """Omite la creación/actualización de cursos y matrículas cuyos docentes no existen en Moodle.

    Retorna ``(cursos_a_crear_filtrados, matriculas_resueltas_filtradas, incidencias)``
    donde cada incidencia contiene los datos para el reporte de usuarios no
    encontrados y cursos no creados:
    ``email, shortname, fullname, firstname, lastname, cat, programa, semestre, grupo``.
    """
    users_by_uname: dict[str, User] = {
        str(u["username"]): u for u in etl_users if u.get("username")
    }
    courses_by_sn: dict[str, dict] = {
        str(c["shortname"]): c for c in etl_courses if c.get("shortname")
    }
    enrols_by_course: dict[str, list[str]] = {}
    for e in enrolments:
        if e.get("course_shortname") and e.get("username"):
            enrols_by_course.setdefault(str(e["course_shortname"]), []).append(str(e["username"]))

    cursos_bloqueados: set[str] = set()
    incidencias: list[dict[str, str]] = []
    vistos: set[tuple[str, str]] = set()

    def _registrar_incidencia(sn: str, etl_uname: str) -> None:
        clave = (sn, etl_uname)
        if clave in vistos:
            return
        vistos.add(clave)
        u = users_by_uname.get(etl_uname, {})
        c = courses_by_sn.get(sn, {})
        parsed = parsear_shortname(sn) or {}
        incidencias.append(
            {
                "email": str(u.get("email") or ""),
                "username": etl_uname,
                "shortname": sn,
                "fullname": str(c.get("fullname") or ""),
                "firstname": str(u.get("firstname") or ""),
                "lastname": str(u.get("lastname") or ""),
                "cat": str(parsed.get("cat_prefix") or ""),
                "programa": str(parsed.get("cod_prog") or ""),
                "semestre": str(parsed.get("semestre") or ""),
                "grupo": str(parsed.get("grupo") or ""),
            }
        )

    def _filtrar_lista_cursos(items: list[dict]) -> list[dict]:
        filtrados: list[dict] = []
        for item in items:
            sn = str(item.get("shortname") or "")
            docentes_curso = enrols_by_course.get(sn, [])
            faltantes = [u for u in docentes_curso if u not in username_map]
            if faltantes:
                cursos_bloqueados.add(sn)
                for etl_uname in faltantes:
                    _registrar_incidencia(sn, etl_uname)
                continue
            filtrados.append(item)
        return filtrados

    cursos_filtrados = _filtrar_lista_cursos(to_create)
    if to_update is not None:
        to_update[:] = _filtrar_lista_cursos(list(to_update))
    if to_activate is not None:
        to_activate[:] = _filtrar_lista_cursos(list(to_activate))

    matriculas_filtradas: list[Enrolment] = []
    for enr in enrolments:
        sn = str(enr.get("course_shortname") or "")
        etl_uname = str(enr.get("username") or "")
        if etl_uname not in username_map or sn in cursos_bloqueados:
            if etl_uname not in username_map and etl_uname:
                _registrar_incidencia(sn, etl_uname)
            continue
        matriculas_filtradas.append({**enr, "username": username_map[etl_uname]})

    return cursos_filtrados, matriculas_filtradas, incidencias
