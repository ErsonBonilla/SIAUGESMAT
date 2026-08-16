import pytest

from app.services.validador_csv import (
    validar_csv_categorias,
    validar_csv_usuarios,
    validar_y_parsear_csv,
)


class TestValidateAndParseCsv:
    def test_valid(self):
        result = validar_y_parsear_csv("shortname\nCURSE_101\nCURSE_102\n", "shortname", "cursos")
        assert result == ["CURSE_101", "CURSE_102"]

    def test_empty_csv(self):
        with pytest.raises(ValueError, match="No se encontraron cursos"):
            validar_y_parsear_csv("shortname\n", "shortname", "cursos")

    def test_missing_column(self):
        with pytest.raises(ValueError, match="Falta la columna requerida: 'shortname'"):
            validar_y_parsear_csv("name\nvalue\n", "shortname", "cursos")

    def test_empty_value(self):
        with pytest.raises(ValueError, match="vac"):
            validar_y_parsear_csv("shortname\n  \nCURSE_101\n", "shortname", "cursos")

    def test_case_insensitive(self):
        result = validar_y_parsear_csv("ShortName\nCURSE_101\n", "shortname", "cursos")
        assert result == ["CURSE_101"]


class TestValidateUsersCsv:
    def test_valid(self):
        csv = "username,firstname,lastname,email,role1\njdoe,John,Doe,jdoe@test.com,teacher\n"
        result = validar_csv_usuarios(csv)
        assert len(result) == 1
        assert result[0]["username"] == "jdoe"

    def test_without_role(self):
        csv = "username,firstname,lastname,email\njdoe,John,Doe,jdoe@test.com\n"
        result = validar_csv_usuarios(csv, default_role="editingteacher")
        assert result[0]["role1"] == "editingteacher"

    def test_missing_required_column(self):
        csv = "username,firstname,lastname\njdoe,John,Doe\n"
        with pytest.raises(ValueError, match="Faltan columnas requeridas"):
            validar_csv_usuarios(csv, default_role="teacher")

    def test_empty_value(self):
        csv = "username,firstname,lastname,email,role1\njdoe,,Doe,jdoe@test.com,teacher\n"
        with pytest.raises(ValueError, match="'firstname' vac"):
            validar_csv_usuarios(csv)

    def test_no_users(self):
        csv = "username,firstname,lastname,email,role1\n"
        with pytest.raises(ValueError, match="No se encontraron usuarios"):
            validar_csv_usuarios(csv)

    def test_with_default_role(self):
        csv = "username,firstname,lastname,email\njdoe,John,Doe,jdoe@test.com\n"
        result = validar_csv_usuarios(csv, default_role="editingteacher")
        assert result[0]["role1"] == "editingteacher"

    def test_with_role_column(self):
        csv = "username,firstname,lastname,email,role1\njdoe,John,Doe,jdoe@test.com,teacher\n"
        result = validar_csv_usuarios(csv)
        assert result[0]["role1"] == "teacher"

    def test_role_preserved(self):
        csv = "username,firstname,lastname,email,role1\njdoe,John,Doe,jdoe@test.com,manager\n"
        result = validar_csv_usuarios(csv)
        assert result[0]["role1"] == "manager"


class TestValidateCategoriesCsv:
    def test_valid(self):
        result = validar_csv_categorias("name,idnumber\nCat One,CAT_01\n")
        assert len(result) == 1
        assert result[0]["name"] == "Cat One"
        assert result[0]["idnumber"] == "CAT_01"

    def test_missing_name_column(self):
        with pytest.raises(ValueError, match="Falta la columna requerida: 'name'"):
            validar_csv_categorias("idnumber\nCAT_01\n")

    def test_empty_name(self):
        with pytest.raises(ValueError, match="'name' vac"):
            validar_csv_categorias("name\n  \n")

    def test_no_categories(self):
        with pytest.raises(ValueError, match="No se encontraron categor"):
            validar_csv_categorias("name\n")

    def test_with_optional_fields(self):
        csv = "name,idnumber,parent,visible,description\nCat One,CAT_01,,1,Desc\n"
        result = validar_csv_categorias(csv)
        assert result[0]["visible"] == 1
        assert result[0]["parent"] == ""
        assert result[0]["description"] == "Desc"
