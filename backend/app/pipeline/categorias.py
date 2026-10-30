"""Clasificación y filtrado de categorías (FASE 1 y FASE 2) — transformaciones puras."""

Category = dict[str, object]


def obtener_ids_subarbol_idead(
    categorias: list[Category],
    *,
    nombre_raiz: str = "IDEAD",
    idnumber_raiz: str = "Distancia",
) -> set[int]:
    """Devuelve los IDs de la categoría raíz IDEAD (idnumber 'Distancia' o 'IDEAD') y todas sus subcategorías.

    Ignora cualquier categoría que esté fuera del árbol de ``IDEAD`` / ``Distancia``.
    """
    raices: set[int] = set()
    hijos_por_padre: dict[int, list[int]] = {}

    nombre_objetivo = nombre_raiz.strip().upper()
    idnumbers_objetivo = {idnumber_raiz.strip().lower(), nombre_objetivo.lower()}

    for cat in categorias:
        raw_id = cat.get("id")
        if raw_id is None:
            continue
        cat_id = int(raw_id)
        parent_id = int(cat.get("parent") or 0)
        hijos_por_padre.setdefault(parent_id, []).append(cat_id)

        idn = str(cat.get("idnumber") or "").strip().lower()
        name = str(cat.get("name") or "").strip().upper()
        if idn in idnumbers_objetivo or (name == nombre_objetivo and parent_id == 0):
            raices.add(cat_id)

    visitados: set[int] = set()
    cola = list(raices)
    while cola:
        actual = cola.pop()
        if actual in visitados:
            continue
        visitados.add(actual)
        for hijo_id in hijos_por_padre.get(actual, []):
            if hijo_id not in visitados:
                cola.append(hijo_id)

    return visitados


def resolver_jerarquia_subcategorias(
    category_id: int,
    categorias: list[Category],
    parsed_shortname: dict[str, str | None] | None = None,
    cat_names_fallback: dict[str, str] | None = None,
) -> dict[str, str]:
    """Resuelve los 3 niveles de subcategorías bajo IDEAD (CAT, Programa, Semestre).

    Combina la cadena de ancestros (``parent``) desde ``category_id`` con la
    búsqueda por ``idnumber`` canónico y aplica fallback a los segmentos del
    ``shortname`` del curso cuando falte algún nivel en Moodle.
    """
    por_id: dict[int, Category] = {}
    por_idnumber: dict[str, Category] = {}
    raices_idead: set[int] = set()

    for cat in categorias:
        raw_id = cat.get("id")
        if raw_id is not None:
            cid = int(raw_id)
            por_id[cid] = cat
            idn_lower = str(cat.get("idnumber") or "").strip().lower()
            name_upper = str(cat.get("name") or "").strip().upper()
            parent_id = int(cat.get("parent") or 0)
            if idn_lower in ("distancia", "idead") or (name_upper == "IDEAD" and parent_id == 0):
                raices_idead.add(cid)
        raw_idn = str(cat.get("idnumber") or "").strip()
        if raw_idn:
            por_idnumber[raw_idn.lower()] = cat

    ancestros: list[Category] = []
    actual_id = category_id
    visitados: set[int] = set()
    while actual_id and actual_id in por_id and actual_id not in visitados:
        visitados.add(actual_id)
        if actual_id in raices_idead:
            break
        cat_obj = por_id[actual_id]
        parent_id = int(cat_obj.get("parent") or 0)
        if parent_id == 0 and str(cat_obj.get("name") or "").strip().upper() == "IDEAD":
            break
        ancestros.append(cat_obj)
        actual_id = parent_id
    ancestros.reverse()  # [CAT, Programa, Semestre]

    cat_prefix = str((parsed_shortname or {}).get("cat_prefix") or "")
    cod_prog = str((parsed_shortname or {}).get("cod_prog") or "")
    semestre = str((parsed_shortname or {}).get("semestre") or "")

    cat_idn_esperado = cat_prefix
    prog_idn_esperado = f"{cat_prefix}_{cod_prog}" if cat_prefix and cod_prog else cod_prog
    sem_idn_esperado = (
        f"{cat_prefix}_{cod_prog}_s{semestre}"
        if cat_prefix and cod_prog and semestre
        else (f"s{semestre}" if semestre else "")
    )

    cat_node = (por_idnumber.get(cat_idn_esperado.lower()) if cat_idn_esperado else None) or (
        ancestros[0] if len(ancestros) >= 1 else None
    )

    prog_node = (por_idnumber.get(prog_idn_esperado.lower()) if prog_idn_esperado else None) or (
        ancestros[1] if len(ancestros) >= 2 else None
    )

    sem_node = (por_idnumber.get(sem_idn_esperado.lower()) if sem_idn_esperado else None) or (
        ancestros[2] if len(ancestros) >= 3 else None
    )

    fallback_map = cat_names_fallback or {}
    cat_shortname = str((cat_node or {}).get("idnumber") or cat_idn_esperado or "")
    cat_name = str((cat_node or {}).get("name") or fallback_map.get(cat_prefix, cat_prefix) or "")

    program_shortname = str((prog_node or {}).get("idnumber") or prog_idn_esperado or "")
    program_name = str((prog_node or {}).get("name") or cod_prog or "")

    semester_shortname = str((sem_node or {}).get("idnumber") or sem_idn_esperado or "")
    semester_name = str(
        (sem_node or {}).get("name") or (f"SEMESTRE {semestre}" if semestre else "")
    )

    return {
        "cat_shortname": cat_shortname,
        "cat_name": cat_name,
        "semester_shortname": semester_shortname,
        "semester_name": semester_name,
        "program_shortname": program_shortname,
        "program_name": program_name,
    }


def clasificar_categorias(
    etl_categories: list[Category],
    existing_idnumbers: set,
    all_categories_map: dict[str, Category],
) -> tuple[list[Category], list[dict[str, object]]]:
    """Separa las categorías ETL en `missing` (a crear) y `relocate`.

    Una categoría existente se marca para reubicar cuando su parent actual en
    Moodle difiere del esperado en el ETL (y el esperado es distinto de root).

    Retorna (missing_categories, categories_to_relocate).
    """
    missing: list[Category] = []
    relocate: list[dict[str, object]] = []

    id_to_idnumber = {
        int(v["id"]): str(k) for k, v in all_categories_map.items() if v.get("id") is not None
    }
    existing_lower = {str(x).lower() for x in existing_idnumbers}
    map_lower = {str(k).lower(): v for k, v in all_categories_map.items()}

    for cat in etl_categories:
        idn = str(cat.get("idnumber", ""))
        if idn not in existing_idnumbers and idn.lower() not in existing_lower:
            missing.append(cat)
            continue

        existing = all_categories_map.get(idn) or map_lower.get(idn.lower(), {})
        moodle_id = existing.get("id")
        if moodle_id is None:
            continue
        actual_parent_id = int(existing.get("parent") or 0)
        expected_parent_idn = str(cat.get("parent", ""))
        actual_parent_idn = str(id_to_idnumber.get(actual_parent_id, ""))

        if (
            expected_parent_idn
            and expected_parent_idn != "0"
            and actual_parent_idn.lower() != expected_parent_idn.lower()
        ):
            relocate.append(
                {
                    "idnumber": idn,
                    "moodle_id": int(moodle_id),
                    "expected_parent_idn": expected_parent_idn,
                    "actual_parent_idn": actual_parent_idn or "root",
                    "cat_data": cat,
                }
            )

    return missing, relocate
