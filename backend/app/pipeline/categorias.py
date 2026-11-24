"""Clasificación y filtrado de categorías (FASE 1 y FASE 2) — transformaciones puras."""

Category = dict[str, object]


def _es_raiz_idead(
    cat: Category,
    *,
    nombre_objetivo: str = "IDEAD",
    idnumbers_objetivo: set[str] | tuple[str, ...] = ("distancia", "idead"),
) -> bool:
    """Determina si una categoría corresponde a la raíz IDEAD / Distancia."""
    idn = str(cat.get("idnumber") or "").strip().lower()
    if idn in idnumbers_objetivo:
        return True
    name = str(cat.get("name") or "").strip().upper()
    parent_id = int(cat.get("parent") or 0)
    return name == nombre_objetivo and parent_id == 0


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

        if _es_raiz_idead(
            cat, nombre_objetivo=nombre_objetivo, idnumbers_objetivo=idnumbers_objetivo
        ):
            raices.add(cat_id)

    visitados: set[int] = set()
    cola = list(raices)
    while cola:
        actual = cola.pop()
        if actual in visitados:
            continue
        visitados.add(actual)
        cola.extend(h for h in hijos_por_padre.get(actual, []) if h not in visitados)

    return visitados


def _indexar_categorias(
    categorias: list[Category],
) -> tuple[dict[int, Category], dict[str, Category], set[int]]:
    """Indexa categorías por id, por idnumber en minúsculas e identifica raíces IDEAD."""
    por_id: dict[int, Category] = {}
    por_idnumber: dict[str, Category] = {}
    raices_idead: set[int] = set()

    for cat in categorias:
        raw_id = cat.get("id")
        if raw_id is not None:
            cid = int(raw_id)
            por_id[cid] = cat
            if _es_raiz_idead(cat):
                raices_idead.add(cid)
        raw_idn = str(cat.get("idnumber") or "").strip()
        if raw_idn:
            por_idnumber[raw_idn.lower()] = cat

    return por_id, por_idnumber, raices_idead


def _construir_ancestros(
    category_id: int,
    por_id: dict[int, Category],
    raices_idead: set[int],
) -> list[Category]:
    """Construye la cadena ordenada [CAT, Programa, Semestre] bajo la raíz IDEAD."""
    ancestros: list[Category] = []
    actual_id = category_id
    visitados: set[int] = set()
    while actual_id and actual_id in por_id and actual_id not in visitados:
        visitados.add(actual_id)
        if actual_id in raices_idead:
            break
        cat_obj = por_id[actual_id]
        if _es_raiz_idead(cat_obj):
            break
        ancestros.append(cat_obj)
        actual_id = int(cat_obj.get("parent") or 0)
    ancestros.reverse()
    return ancestros


def _idnumbers_esperados(cat_prefix: str, cod_prog: str, semestre: str) -> tuple[str, str, str]:
    """Deriva los idnumbers canónicos esperados para CAT, Programa y Semestre."""
    prog_idn = f"{cat_prefix}_{cod_prog}" if cat_prefix and cod_prog else cod_prog
    if cat_prefix and cod_prog and semestre:
        sem_idn = f"{cat_prefix}_{cod_prog}_s{semestre}"
    elif semestre:
        sem_idn = f"s{semestre}"
    else:
        sem_idn = ""
    return cat_prefix, prog_idn, sem_idn


def _elegir_nodo(
    por_idnumber: dict[str, Category],
    idn_esperado: str,
    ancestros: list[Category],
    nivel: int,
) -> Category:
    """Selecciona el nodo por idnumber canónico o por posición en la cadena de ancestros."""
    if idn_esperado:
        encontrado = por_idnumber.get(idn_esperado.lower())
        if encontrado:
            return encontrado
    if nivel < len(ancestros):
        return ancestros[nivel]
    return {}


def _campo_nodo(nodo: Category, clave: str, respaldo: str) -> str:
    """Extrae un campo de texto del nodo de categoría o aplica el valor de respaldo."""
    valor = nodo.get(clave)
    return str(valor if valor else respaldo)


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
    por_id, por_idnumber, raices_idead = _indexar_categorias(categorias)
    ancestros = _construir_ancestros(category_id, por_id, raices_idead)

    segmentos = parsed_shortname or {}
    cat_prefix = _campo_nodo(segmentos, "cat_prefix", "")
    cod_prog = _campo_nodo(segmentos, "cod_prog", "")
    semestre = _campo_nodo(segmentos, "semestre", "")

    cat_idn, prog_idn, sem_idn = _idnumbers_esperados(cat_prefix, cod_prog, semestre)

    cat_node = _elegir_nodo(por_idnumber, cat_idn, ancestros, 0)
    prog_node = _elegir_nodo(por_idnumber, prog_idn, ancestros, 1)
    sem_node = _elegir_nodo(por_idnumber, sem_idn, ancestros, 2)

    fallback_map = cat_names_fallback or {}
    sem_fallback = f"SEMESTRE {semestre}" if semestre else ""

    return {
        "cat_shortname": _campo_nodo(cat_node, "idnumber", cat_idn),
        "cat_name": _campo_nodo(cat_node, "name", fallback_map.get(cat_prefix, cat_prefix)),
        "semester_shortname": _campo_nodo(sem_node, "idnumber", sem_idn),
        "semester_name": _campo_nodo(sem_node, "name", sem_fallback),
        "program_shortname": _campo_nodo(prog_node, "idnumber", prog_idn),
        "program_name": _campo_nodo(prog_node, "name", cod_prog),
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
