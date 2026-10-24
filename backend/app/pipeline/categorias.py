"""Clasificación y filtrado de categorías (FASE 1 y FASE 2) — transformaciones puras."""

Category = dict[str, object]


def obtener_ids_subarbol_idead(
    categorias: list[Category],
    *,
    nombre_raiz: str = "IDEAD",
    idnumber_raiz: str = "Distancia",
) -> set[int]:
    """Devuelve los IDs de la categoría raíz IDEAD (idnumber 'Distancia') y todas sus subcategorías.

    Ignora cualquier categoría que esté fuera del árbol de ``IDEAD`` / ``Distancia``.
    """
    raices: set[int] = set()
    hijos_por_padre: dict[int, list[int]] = {}

    nombre_objetivo = nombre_raiz.strip().upper()
    idnumber_objetivo = idnumber_raiz.strip().lower()

    for cat in categorias:
        raw_id = cat.get("id")
        if raw_id is None:
            continue
        cat_id = int(raw_id)
        parent_id = int(cat.get("parent") or 0)
        hijos_por_padre.setdefault(parent_id, []).append(cat_id)

        idn = str(cat.get("idnumber") or "").strip().lower()
        name = str(cat.get("name") or "").strip().upper()
        if idn == idnumber_objetivo or (name == nombre_objetivo and parent_id == 0):
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
