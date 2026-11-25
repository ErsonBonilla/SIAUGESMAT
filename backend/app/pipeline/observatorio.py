"""Agregación pura del Observatorio IDEAD Colombia (Departamento -> Municipio/CAT -> Programa -> Estudiantes únicos)."""

from app.pipeline.catalogo_divipola import (
    normalizar_texto_geografico,
    resolver_ubicacion_cat,
)
from app.pipeline.categorias import (
    obtener_ids_subarbol_idead,
    resolver_jerarquia_subcategorias,
)
from app.pipeline.nombres_cortos import SIAUGESMAT_PATTERN, parsear_shortname

ROLES_DOCENTE_SHORTNAME = {"editingteacher", "teacher", "manager", "coursecreator"}
ROLES_DOCENTE_ID = {1, 2, 3, 4}

NOMBRES_CAT_RESPALDO = {
    "IBA": "IBAGUE",
    "CHA": "CHAPARRAL",
    "HON": "HONDA",
    "MEL": "MELGAR",
    "MAR": "MARIQUITA",
    "FRE": "FRESNO",
    "PLA": "PLANADAS",
    "RIO": "RIOBLANCO",
    "CAJ": "CAJAMARCA",
    "PUR": "PURIFICACION",
    "LIB": "LIBANO",
    "ESP": "ESPINAL",
    "GUA": "GUAMO",
    "ORT": "ORTEGA",
    "ATA": "ATACO",
    "ROV": "ROVIRA",
    "CUN": "CUNDAY",
    "ICO": "ICONONZO",
    "VEN": "VENADILLO",
    "LER": "LERIDA",
    "ARM": "ARMERO",
    "URA": "URABA",
    "MED": "MEDELLIN",
    "BOG": "BOGOTA",
    "TUN": "TUNAL",
    "KEN": "KENNEDY",
    "SUB": "SUBA",
    "SIB": "SIBATE",
    "GIR": "GIRARDOT",
    "FUS": "FUSAGASUGA",
    "PER": "PEREIRA",
    "CAL": "CALI",
    "NEI": "NEIVA",
    "POP": "POPAYAN",
    "VIL": "VILLAVICENCIO",
    "MOC": "MOCOA",
    "QUI": "QUIBDO",
    "TUM": "TUMACO",
}


def _rol_es_docente(rol: dict) -> bool:
    shortname = str(rol.get("shortname") or "").strip().lower()
    if shortname in ROLES_DOCENTE_SHORTNAME:
        return True
    raw_id = rol.get("roleid")
    if raw_id is not None and str(raw_id).isdigit():
        return int(raw_id) in ROLES_DOCENTE_ID
    return False


def _tiene_rol_docente_en_lista(roles: object) -> bool:
    if not isinstance(roles, list):
        return False
    return any(_rol_es_docente(r) for r in roles if isinstance(r, dict))


def _esta_en_docentes_respaldo(usuario: dict, docentes_respaldo: set[str]) -> bool:
    identificadores = {
        str(usuario.get("id") or "").strip(),
        str(usuario.get("username") or "").strip().lower(),
    }
    identificadores.discard("")
    return bool(identificadores & docentes_respaldo)


def es_rol_docente_o_gestor(usuario: dict, docentes_respaldo: set[str] | None = None) -> bool:
    """Determina si un usuario matriculado tiene rol de docente o gestor en el curso."""
    if _tiene_rol_docente_en_lista(usuario.get("roles")):
        return True
    if not docentes_respaldo:
        return False
    return _esta_en_docentes_respaldo(usuario, docentes_respaldo)


def _clave_estudiante(usuario: dict) -> str:
    raw_id = usuario.get("id")
    if raw_id is not None and str(raw_id).strip():
        return f"id:{str(raw_id).strip()}"
    uname = str(usuario.get("username") or "").strip().lower()
    return f"u:{uname}" if uname else ""


def separar_docentes_y_estudiantes_curso(
    matriculados: list[dict],
    docentes_respaldo: set[str] | None = None,
) -> tuple[bool, set[str]]:
    """Separa los matriculados de un curso en (tiene_docente, conjunto_claves_estudiantes)."""
    tiene_docente = bool(docentes_respaldo)
    estudiantes: set[str] = set()
    for u in matriculados:
        if es_rol_docente_o_gestor(u, docentes_respaldo):
            tiene_docente = True
            continue
        clave = _clave_estudiante(u)
        if clave:
            estudiantes.add(clave)
    return tiene_docente, estudiantes


def _curso_es_elegible_idead(curso: dict, ids_idead: set[int]) -> bool:
    if not ids_idead or int(curso.get("visible", 1)) == 0:
        return False
    sn = str(curso.get("shortname") or "")
    if not SIAUGESMAT_PATTERN.match(sn):
        return False
    raw_cat = curso.get("categoryid")
    if raw_cat is None:
        raw_cat = curso.get("category", 0)
    return int(raw_cat or 0) in ids_idead


def _etiqueta_municipio_cat(mpio_name: str, cat_name: str) -> str:
    norm_mpio = normalizar_texto_geografico(mpio_name)
    norm_cat = normalizar_texto_geografico(cat_name)
    if not norm_cat or norm_cat == norm_mpio or norm_cat in norm_mpio:
        return mpio_name
    return f"{mpio_name} ({cat_name})"


def _serializar_departamentos(acumulador: dict[str, dict]) -> tuple[list[dict], int, int]:
    salida_dptos: list[dict] = []
    total_cats = 0
    total_programs = 0

    for d_code, d_data in sorted(acumulador.items(), key=lambda x: x[1]["dpto_name"]):
        lista_cats: list[dict] = []
        for _c_key, c_data in sorted(d_data["cats"].items(), key=lambda x: x[1]["display_name"]):
            lista_progs: list[dict] = []
            for _p_code, p_data in sorted(
                c_data["programs"].items(), key=lambda x: x[1]["program_name"]
            ):
                lista_progs.append(
                    {
                        "program_code": p_data["program_code"],
                        "program_name": p_data["program_name"],
                        "students_count": len(p_data["students"]),
                        "courses_count": p_data["courses_count"],
                    }
                )
            total_programs += len(lista_progs)
            lista_cats.append(
                {
                    "mpio_code": c_data["mpio_code"],
                    "mpio_name": c_data["mpio_name"],
                    "cat_name": c_data["cat_name"],
                    "cat_shortname": c_data["cat_shortname"],
                    "display_name": c_data["display_name"],
                    "lat": c_data["lat"],
                    "lon": c_data["lon"],
                    "programs_count": len(lista_progs),
                    "students_count": len(c_data["students"]),
                    "programs": lista_progs,
                }
            )
        total_cats += len(lista_cats)
        salida_dptos.append(
            {
                "dpto_code": d_code,
                "dpto_name": d_data["dpto_name"],
                "cats_count": len(lista_cats),
                "students_count": len(d_data["students"]),
                "municipalities": lista_cats,
            }
        )

    return salida_dptos, total_cats, total_programs


def _texto_prioritario(*valores: object, respaldo: str = "") -> str:
    for v in valores:
        if v is not None and v != "":
            return str(v)
    return respaldo


def _resolver_metadatos_curso(
    curso: dict, categorias: list[dict]
) -> tuple[dict[str, object] | None, str, str, str, str]:
    sn = _texto_prioritario(curso.get("shortname"))
    parsed = parsear_shortname(sn) or {}
    cat_id = int(_texto_prioritario(curso.get("categoryid"), curso.get("category"), respaldo="0"))
    jerarquia = resolver_jerarquia_subcategorias(cat_id, categorias, parsed, NOMBRES_CAT_RESPALDO)
    cat_short = _texto_prioritario(jerarquia.get("cat_shortname"), parsed.get("cat_prefix")).upper()
    cat_name = _texto_prioritario(jerarquia.get("cat_name"), respaldo=cat_short).upper()
    prog_code = _texto_prioritario(
        parsed.get("cod_prog"), jerarquia.get("program_shortname"), respaldo="0000"
    )
    prog_name = _texto_prioritario(jerarquia.get("program_name"), respaldo=prog_code).upper()
    return resolver_ubicacion_cat(cat_name, cat_short), cat_short, cat_name, prog_code, prog_name


def _registrar_curso_en_acumulador(
    acumulador: dict[str, dict],
    ubicacion: dict[str, object],
    cat_short: str,
    cat_name: str,
    prog_code: str,
    prog_name: str,
    estudiantes_curso: set[str],
) -> str:
    d_code = str(ubicacion["dpto_code"])
    m_code = str(ubicacion["mpio_code"])
    m_name = str(ubicacion["mpio_name"])

    dpto_entry = acumulador.setdefault(
        d_code,
        {
            "dpto_code": d_code,
            "dpto_name": str(ubicacion["dpto_name"]),
            "students": set(),
            "cats": {},
        },
    )
    clave_cat = f"{m_code}:{cat_short or cat_name}"
    cat_entry = dpto_entry["cats"].setdefault(
        clave_cat,
        {
            "mpio_code": m_code,
            "mpio_name": m_name,
            "cat_name": cat_name,
            "cat_shortname": cat_short or m_code,
            "display_name": _etiqueta_municipio_cat(m_name, cat_name),
            "lat": float(ubicacion["lat"]),
            "lon": float(ubicacion["lon"]),
            "students": set(),
            "programs": {},
        },
    )
    prog_entry = cat_entry["programs"].setdefault(
        prog_code,
        {
            "program_code": prog_code,
            "program_name": prog_name,
            "students": set(),
            "courses_count": 0,
        },
    )

    prog_entry["courses_count"] += 1
    prog_entry["students"].update(estudiantes_curso)
    cat_entry["students"].update(estudiantes_curso)
    dpto_entry["students"].update(estudiantes_curso)
    return m_code


def construir_censo_observatorio(
    cursos: list[dict],
    categorias: list[dict],
    matriculados_por_curso: dict[int, list[dict]],
    docentes_por_curso: dict[int, set[str]] | None = None,
    actualizado_en: str = "",
) -> dict[str, object]:
    """Construye la jerarquía Colombia -> Departamento -> Municipio (CAT) -> Programa -> Estudiantes."""
    ids_idead = obtener_ids_subarbol_idead(categorias) if categorias else set()
    categorias_idead = [
        c for c in categorias if c.get("id") is not None and int(c["id"]) in ids_idead
    ]
    mapa_respaldo_doc = docentes_por_curso or {}

    acumulador: dict[str, dict] = {}
    estudiantes_globales: set[str] = set()
    municipios_unicos: set[str] = set()
    cursos_activos = 0

    for curso in cursos:
        if not _curso_es_elegible_idead(curso, ids_idead):
            continue
        cid = int(curso.get("id") or 0)
        tiene_docente, estudiantes_curso = separar_docentes_y_estudiantes_curso(
            matriculados_por_curso.get(cid, []), mapa_respaldo_doc.get(cid)
        )
        if not tiene_docente:
            continue

        ubicacion, cat_short, cat_name, prog_code, prog_name = _resolver_metadatos_curso(
            curso, categorias_idead
        )
        if not ubicacion:
            continue

        cursos_activos += 1
        m_code = _registrar_curso_en_acumulador(
            acumulador, ubicacion, cat_short, cat_name, prog_code, prog_name, estudiantes_curso
        )
        municipios_unicos.add(m_code)
        estudiantes_globales.update(estudiantes_curso)

    departamentos, total_cats, total_programs = _serializar_departamentos(acumulador)

    return {
        "total_students": len(estudiantes_globales),
        "total_departments": len(departamentos),
        "total_municipalities": len(municipios_unicos),
        "total_cats": total_cats,
        "total_programs": total_programs,
        "total_courses": cursos_activos,
        "updated_at": actualizado_en,
        "departments": departamentos,
    }
