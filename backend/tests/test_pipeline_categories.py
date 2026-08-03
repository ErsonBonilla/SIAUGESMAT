"""Pruebas del núcleo puro de clasificación de categorías."""
from app.pipeline.categories import classify_categories


def _cat(idnumber="IDE", parent=""):
    return {"name": "Test", "idnumber": idnumber, "parent": parent}


class TestClassifyCategories:
    def test_missing_category_detected(self):
        missing, relocate = classify_categories([_cat()], set(), {})
        assert len(missing) == 1
        assert missing[0]["idnumber"] == "IDE"
        assert relocate == []

    def test_existing_category_not_missing(self):
        missing, _ = classify_categories(
            [_cat()], {"IDE"}, {"IDE": {"id": 1, "parent": 0}},
        )
        assert missing == []

    def test_existing_category_with_wrong_parent_relocated(self):
        _, relocate = classify_categories(
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
        _, relocate = classify_categories(
            [_cat(parent="ROOT")],
            {"IDE", "PADRE"},
            {"IDE": {"id": 1, "parent": 7}, "PADRE": {"id": 7}},
        )
        assert len(relocate) == 1
        assert relocate[0]["actual_parent_idn"] == "PADRE"
        assert relocate[0]["expected_parent_idn"] == "ROOT"

    def test_correct_parent_not_relocated(self):
        _, relocate = classify_categories(
            [_cat(parent="PADRE")],
            {"IDE", "PADRE"},
            {"IDE": {"id": 1, "parent": 7}, "PADRE": {"id": 7}},
        )
        assert relocate == []

    def test_root_parent_not_relocated(self):
        _, relocate = classify_categories(
            [_cat(parent="0")],
            {"IDE"},
            {"IDE": {"id": 1, "parent": 0}},
        )
        assert relocate == []

    def test_multiple_categories(self):
        missing, relocate = classify_categories(
            [_cat("A"), _cat("B")],
            {"B"},
            {"B": {"id": 2, "parent": 0}},
        )
        assert [c["idnumber"] for c in missing] == ["A"]
        assert relocate == []
