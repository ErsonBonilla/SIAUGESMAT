"""Clasificación de categorías (FASE 2) — transformaciones puras."""

Category = dict[str, object]


def classify_categories(
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

    id_to_idnumber = {v["id"]: k for k, v in all_categories_map.items()}

    for cat in etl_categories:
        idn = cat.get("idnumber", "")
        if idn not in existing_idnumbers:
            missing.append(cat)
            continue

        existing = all_categories_map.get(idn, {})
        actual_parent_id = existing.get("parent", 0)
        expected_parent_idn = cat.get("parent", "")
        actual_parent_idn = id_to_idnumber.get(actual_parent_id, "")

        if (
            expected_parent_idn
            and str(expected_parent_idn) != "0"
            and actual_parent_idn != expected_parent_idn
        ):
            relocate.append({
                "idnumber": idn,
                "moodle_id": existing.get("id"),
                "expected_parent_idn": expected_parent_idn,
                "actual_parent_idn": actual_parent_idn or "root",
                "cat_data": cat,
            })

    return missing, relocate
