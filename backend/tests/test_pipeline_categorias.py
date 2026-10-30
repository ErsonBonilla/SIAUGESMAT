"""Pruebas del núcleo puro de clasificación de categorías."""

from app.pipeline.categorias import (
    clasificar_categorias,
    obtener_ids_subarbol_idead,
    resolver_jerarquia_subcategorias,
)


def _cat(idnumber="IDE", parent=""):
    return {"name": "Test", "idnumber": idnumber, "parent": parent}


class TestClassifyCategories:
    def test_missing_category_detected(self):
        missing, relocate = clasificar_categorias([_cat()], set(), {})
        assert len(missing) == 1
        assert missing[0]["idnumber"] == "IDE"
        assert relocate == []

    def test_existing_category_not_missing(self):
        missing, _ = clasificar_categorias(
            [_cat()],
            {"IDE"},
            {"IDE": {"id": 1, "parent": 0}},
        )
        assert missing == []

    def test_existing_category_with_wrong_parent_relocated(self):
        _, relocate = clasificar_categorias(
            [_cat(parent="PADRE")],
            {"IDE"},
            {"IDE": {"id": 1, "parent": 5}},
        )
        assert len(relocate) == 1
        item = relocate[0]
        assert item["idnumber"] == "IDE"
        assert item["moodle_id"] == 1
        assert item["actual_parent_idn"] == "root"  # parent 5 sin idnumber conocido
        assert item["cat_data"]["idnumber"] == "IDE"

    def test_relocate_uses_idnumber_map_for_parent(self):
        _, relocate = clasificar_categorias(
            [_cat(parent="ROOT")],
            {"IDE", "PADRE"},
            {"IDE": {"id": 1, "parent": 7}, "PADRE": {"id": 7}},
        )
        assert len(relocate) == 1
        assert relocate[0]["actual_parent_idn"] == "PADRE"
        assert relocate[0]["expected_parent_idn"] == "ROOT"

    def test_correct_parent_not_relocated(self):
        _, relocate = clasificar_categorias(
            [_cat(parent="PADRE")],
            {"IDE", "PADRE"},
            {"IDE": {"id": 1, "parent": 7}, "PADRE": {"id": 7}},
        )
        assert relocate == []

    def test_root_parent_not_relocated(self):
        _, relocate = clasificar_categorias(
            [_cat(parent="0")],
            {"IDE"},
            {"IDE": {"id": 1, "parent": 0}},
        )
        assert relocate == []

    def test_multiple_categories(self):
        missing, relocate = clasificar_categorias(
            [_cat("A"), _cat("B")],
            {"B"},
            {"B": {"id": 2, "parent": 0}},
        )
        assert [c["idnumber"] for c in missing] == ["A"]
        assert relocate == []


class TestResolverJerarquiaSubcategorias:
    def test_reconoce_raiz_idead_por_idnumber_idead(self):
        cats = [
            {"id": 1, "name": "Raiz", "idnumber": "IDEAD", "parent": 0},
            {"id": 2, "name": "IBAGUE", "idnumber": "IBA", "parent": 1},
            {"id": 3, "name": "EXTERNA", "idnumber": "EXT", "parent": 0},
        ]
        assert obtener_ids_subarbol_idead(cats) == {1, 2}

    def test_resuelve_tres_niveles_desde_categorias_moodle(self):
        cats = [
            {"id": 10, "name": "IDEAD", "idnumber": "DISTANCIA", "parent": 0},
            {"id": 20, "name": "CALI", "idnumber": "CAL", "parent": 10},
            {"id": 30, "name": "INGENIERIA DE SISTEMAS", "idnumber": "CAL_0852", "parent": 20},
            {"id": 40, "name": "SEMESTRE IV", "idnumber": "CAL_0852_sIV", "parent": 30},
        ]
        parsed = {"cat_prefix": "CAL", "cod_prog": "0852", "semestre": "IV"}
        res = resolver_jerarquia_subcategorias(40, cats, parsed)
        assert res == {
            "cat_shortname": "CAL",
            "cat_name": "CALI",
            "semester_shortname": "CAL_0852_sIV",
            "semester_name": "SEMESTRE IV",
            "program_shortname": "CAL_0852",
            "program_name": "INGENIERIA DE SISTEMAS",
        }
