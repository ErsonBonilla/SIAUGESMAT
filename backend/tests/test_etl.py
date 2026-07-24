"""
Pruebas unitarias de la lógica de extracción y transformación (ETL).

Verifica que el DataFrame del Excel se convierta correctamente en las
estructuras de categorías, cursos, usuarios y matrículas, según las
reglas de la Universidad del Tolima.
"""

import pandas as pd
import pytest

from app.services.parsers.base import BaseExcelParser
from app.services.parsers.distancia import DistanciaParser


# ---------------------------------------------------------------------------
# Función auxiliar para construir un DataFrame base con las columnas mínimas
# ---------------------------------------------------------------------------
def _base_dataframe(rows: list[dict]) -> pd.DataFrame:
    """Crea un DataFrame con las columnas esperadas por el ETL."""
    for row in rows:
        row.setdefault("Confirma", "ACEPTA")
    return pd.DataFrame(rows, dtype=str)


# ---------------------------------------------------------------------------
# Escenario 1: curso y docente básicos
# ---------------------------------------------------------------------------
def test_transform_basic():
    """Un curso con docente debe generar las estructuras esperadas."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "105 - Lic. en Matemáticas",
            "Código curso": "202",
            "Semestre": "1",
            "Grupo": "01",
            "Curso": "Matemáticas",
            "Correo Institucional": "juan.perez@ut.edu.co",
            "Docente": "Pérez Juan",
        }
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")

    # Categorías: deben existir los tres niveles sin duplicados
    cats = result["categories"]
    cat_ids = [c["idnumber"] for c in cats]
    assert "IDE" in cat_ids           # nivel 1
    assert "IDE_0105" in cat_ids      # nivel 2
    assert "IDE_0105_sI" in cat_ids   # nivel 3

    # Curso
    courses = result["courses"]
    assert len(courses) == 1
    c = courses[0]
    assert c["shortname"] == "IDE_0105_sI_202_G-01"
    assert c["fullname"] == "MATEMÁTICAS - GRUPO 01"
    assert c["category_idnumber"] == "IDE_0105_sI"
    assert c["format"] == "onetopic"
    assert c["templatecourse"] == "PORTAFOLIO_0105_sI_202"
    # Usuario
    users = result["users"]
    assert len(users) == 1
    u = users[0]
    assert u["username"] == "juan.perez"
    assert u["firstname"] == "Juan"
    assert u["lastname"] == "Pérez"
    assert u["email"] == "juan.perez@ut.edu.co"
    assert u["password"] == ""  # Moodle genera password con createpassword=1
    assert u["city"] == "IDEAD"
    assert u["description"] == ""

    # Matriculación
    enrols = result["enrolments"]
    assert len(enrols) == 1
    assert enrols[0]["username"] == "juan.perez"
    assert enrols[0]["course_shortname"] == "IDE_0105_sI_202_G-01"
    assert enrols[0]["role"] == "editingteacher"


# ---------------------------------------------------------------------------
# Escenario 2: prefijo para "APARTADO"
# ---------------------------------------------------------------------------
def test_apartado_maps_to_uraba_prefix():
    """La categoría APARTADO debe usar el prefijo URA."""
    df = _base_dataframe([
        {
            "CAT": "APARTADO",
            "Programa": "305 - Ing. Física",
            "Código curso": "101",
            "Semestre": "2",
            "Grupo": "02",
            "Curso": "Física",
            "Correo Institucional": "ana@ut.edu.co",
            "Docente": "Ana López",
        }
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    course = result["courses"][0]
    assert course["shortname"] == "URA_0305_sII_101_G-02"
    assert course["category_idnumber"] == "URA_0305_sII"

    cats = result["categories"]
    # La categoría raíz es la modalidad (por defecto DISTANCIA)
    root = [c for c in cats if c["parent"] == 0][0]
    assert root["idnumber"] == "DISTANCIA"
    # URA es hija de DISTANCIA
    ural = [c for c in cats if c["idnumber"] == "URA"]
    assert len(ural) == 1
    assert ural[0]["parent"] == "DISTANCIA"


# ---------------------------------------------------------------------------
# Escenario 3: relleno de cero inicial en código de programa
# ---------------------------------------------------------------------------
def test_code_padding():
    """Un código de programa sin cero inicial se debe completar a 3 dígitos."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "5 - Química",
            "Código curso": "10",
            "Semestre": "1",
            "Grupo": "1",
            "Curso": "Química",
            "Correo Institucional": "x@ut.edu.co",
            "Docente": "X Y",
        }
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    course = result["courses"][0]
    assert course["shortname"] == "IDE_0005_sI_10_G-1"
    assert course["category_idnumber"] == "IDE_0005_sI"


# ---------------------------------------------------------------------------
# Escenario 4: docente sin email válido (@ut.edu.co) no se incluye
# ---------------------------------------------------------------------------
def test_invalid_email_ignored():
    """Un docente sin email @ut.edu.co no debe aparecer en usuarios ni matrículas."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "100 - Test",
            "Código curso": "1",
            "Semestre": "1",
            "Grupo": "1",
            "Curso": "Test",
            "Correo Institucional": "docente@gmail.com",   # no institucional
            "Docente": "Juan Pérez",
        }
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    assert len(result["users"]) == 0
    assert len(result["enrolments"]) == 0


# ---------------------------------------------------------------------------
# Escenario 5: división de nombre completo
# ---------------------------------------------------------------------------
def test_name_splitting():
    """Divide el nombre completo usando el diccionario de nombres propios."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "1 - Test",
            "Código curso": "1",
            "Semestre": "1",
            "Grupo": "1",
            "Curso": "Test",
            "Correo Institucional": "pedro@ut.edu.co",
            "Docente": "García López Pedro Luis",
        }
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    user = result["users"][0]
    assert user["firstname"] == "Pedro Luis"
    assert user["lastname"] == "García López"


# ---------------------------------------------------------------------------
# Escenario 6: nombre con una sola palabra
# ---------------------------------------------------------------------------
def test_single_word_name():
    """Si el nombre solo tiene una palabra, se toma como firstname."""
    df = _base_dataframe([
        {
            "CAT": "X",
            "Programa": "1 - X",
            "Código curso": "1",
            "Semestre": "1",
            "Grupo": "1",
            "Curso": "X",
            "Correo Institucional": "x@ut.edu.co",
            "Docente": "Sol",
        }
    ])
    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    user = result["users"][0]
    assert user["firstname"] == "Sol"
    assert user["lastname"] == "Sol"


# ---------------------------------------------------------------------------
# Escenario 7: jerarquía de categorías ordenada
# ---------------------------------------------------------------------------
def test_category_hierarchy_order():
    """Las categorías deben aparecer en orden de padre antes que hijos."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "200 - Programa A",
            "Código curso": "10",
            "Semestre": "2025",
            "Grupo": "A",
            "Curso": "Curso A",
            "Correo Institucional": "p@ut.edu.co",
            "Docente": "P P",
        }
    ])
    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    cats = result["categories"]
    # El primer elemento debe ser el raíz (parent=0)
    assert cats[0]["parent"] == 0
    # Los últimos deben ser los niveles más profundos
    assert cats[-1]["parent"] != 0


# ---------------------------------------------------------------------------
# Escenario 8: múltiples cursos y usuarios sin duplicados
# ---------------------------------------------------------------------------
def test_multiple_courses_same_program():
    """Varios cursos en el mismo programa comparten las categorías superiores."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "105 - Programa 1",
            "Código curso": "201",
            "Semestre": "1",
            "Grupo": "01",
            "Curso": "Curso 1",
            "Correo Institucional": "doc1@ut.edu.co",
            "Docente": "Doc Uno",
        },
        {
            "CAT": "IDEAD",
            "Programa": "105 - Programa 1",
            "Código curso": "202",
            "Semestre": "1",
            "Grupo": "02",
            "Curso": "Curso 2",
            "Correo Institucional": "doc2@ut.edu.co",
            "Docente": "Doc Dos",
        },
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    cats = result["categories"]
    roots = [c for c in cats if c["parent"] == 0]
    assert len(roots) == 1
    assert roots[0]["idnumber"] == "DISTANCIA"  # modalidad por defecto

    cat_level = [c for c in cats if c["parent"] == "DISTANCIA"]
    assert len(cat_level) == 1
    assert cat_level[0]["idnumber"] == "IDE"

    programs = [c for c in cats if c["parent"] == "IDE"]
    assert len(programs) == 1

    semesters = [c for c in cats if c["parent"] == "IDE_0105"]
    assert len(semesters) == 1
    assert semesters[0]["idnumber"] == "IDE_0105_sI"

    # Cursos
    assert len(result["courses"]) == 2
    # Usuarios
    assert len(result["users"]) == 2
    # Matriculaciones
    assert len(result["enrolments"]) == 2


# ---------------------------------------------------------------------------
# Escenario 9: marcas de eliminación (manejadas desde la app, no del Excel)
# ---------------------------------------------------------------------------
def test_delete_flags():
    """Las marcas de eliminación son siempre False desde el ETL."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "1 - Test",
            "Código curso": "1",
            "Semestre": "1",
            "Grupo": "1",
            "Curso": "Test",
            "Correo Institucional": "t@ut.edu.co",
            "Docente": "T T",
        }
    ])
    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    assert result["courses"][0]["delete"] is False
    assert result["users"][0]["delete"] is False


# ---------------------------------------------------------------------------
# Escenario 10: visibilidad del curso (manejada desde la app, no del Excel)
# ---------------------------------------------------------------------------
def test_course_visibility():
    """El curso siempre se crea visible (1) desde el ETL."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "1 - Test",
            "Código curso": "1",
            "Semestre": "1",
            "Grupo": "1",
            "Curso": "Test",
            "Correo Institucional": "t@ut.edu.co",
            "Docente": "T T",
        }
    ])
    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    assert result["courses"][0]["visible"] == 1


# ---------------------------------------------------------------------------
# Escenario 11: nuevo formato con código de programa en columna Programa
# ---------------------------------------------------------------------------
def test_new_format_with_program_parse():
    """El nuevo formato con Programa='cod - nombre' extrae cod_programa."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "0838 - TECNOLOGIA EN PROTECCION Y RECUPERACION DE ECOSISTEMAS FORESTALES",
            "Código curso": "202",
            "Semestre": "1",
            "Grupo": "01",
            "Curso": "Matemáticas",
            "Correo Institucional": "juan.perez@ut.edu.co",
            "Docente": "Juan Pérez",
        }
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")

    cats = result["categories"]
    cat_ids = [c["idnumber"] for c in cats]
    assert "IDE" in cat_ids
    assert "IDE_0838" in cat_ids
    assert "IDE_0838_sI" in cat_ids

    course = result["courses"][0]
    assert course["shortname"] == "IDE_0838_sI_202_G-01"
    assert course["fullname"] == "MATEMÁTICAS - GRUPO 01"
    assert course["category_idnumber"] == "IDE_0838_sI"
    assert course["templatecourse"] == "PORTAFOLIO_0838_sI_202"

    user = result["users"][0]
    assert user["username"] == "juan.perez"
    assert user["email"] == "juan.perez@ut.edu.co"

    assert len(result["enrolments"]) == 1
    assert result["enrolments"][0]["username"] == "juan.perez"


# ---------------------------------------------------------------------------
# Escenario 12: nuevo formato sin código de programa (solo nombre)
# ---------------------------------------------------------------------------
def test_new_format_without_program_code():
    """Cuando Programa no tiene formato 'cod - nombre', cod_programa queda vacío."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "LICENCIATURA EN MATEMATICAS",
            "Código curso": "202",
            "Semestre": "1",
            "Grupo": "01",
            "Curso": "Matemáticas",
            "Correo Institucional": "juan.perez@ut.edu.co",
            "Docente": "Juan Pérez",
        }
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")

    # Sin código de programa → cod_programa vacío → fallback al código
    course = result["courses"][0]
    assert course["fullname"] == "MATEMÁTICAS - GRUPO 01"

    # La categoría nivel 2 debe usar el nombre completo del programa
    cats = result["categories"]
    cat_level2 = [c for c in cats if "LICENCIATURA EN MATEMATICAS" in c["name"]]
    assert len(cat_level2) == 1


# ---------------------------------------------------------------------------
# Escenario 13: columnas ruidosas deben ser ignoradas
# ---------------------------------------------------------------------------
def test_noise_columns_ignored():
    """Columnas como Categoría, Perfil, Total, Tipo deben ser ignoradas."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "105 - Test",
            "Código curso": "202",
            "Semestre": "1",
            "Grupo": "01",
            "Curso": "Matemáticas",
            "Docente": "Juan Pérez",
            "Correo Institucional": "juan.perez@ut.edu.co",
            "Categoría": "AUXILIAR",
            "Perfil del Curso": "INGENIERO",
            "Total Cursos Docente": "4",
            "Tipo Programa": "PREGRADO",
            "Horas Curso": "30",
        }
    ])

    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    course = result["courses"][0]
    assert course["shortname"] == "IDE_0105_sI_202_G-01"
    assert len(result["users"]) == 1


# ---------------------------------------------------------------------------
# Escenario 14: conversión a número romano
# ---------------------------------------------------------------------------
class TestRomanNumeral:
    """Pruebas unitarias para _to_roman_numeral."""

    def test_arabic_to_roman(self):
        assert BaseExcelParser._to_roman_numeral("1") == "I"
        assert BaseExcelParser._to_roman_numeral("6") == "VI"
        assert BaseExcelParser._to_roman_numeral("12") == "XII"

    def test_roman_passthrough(self):
        assert BaseExcelParser._to_roman_numeral("I") == "I"
        assert BaseExcelParser._to_roman_numeral("VI") == "VI"
        assert BaseExcelParser._to_roman_numeral("iii") == "III"

    def test_out_of_range_fallback(self):
        assert BaseExcelParser._to_roman_numeral("2025") == "2025"
        assert BaseExcelParser._to_roman_numeral("0") == "0"

    def test_non_numeric_fallback(self):
        assert BaseExcelParser._to_roman_numeral("custom") == "CUSTOM"


# ---------------------------------------------------------------------------
# Escenario 15: estructura mínima de curso
# ---------------------------------------------------------------------------
def test_course_minimal_fields():
    """Todo curso debe incluir los campos obligatorios para Moodle 3.9."""
    df = _base_dataframe([
        {
            "CAT": "IDEAD",
            "Programa": "105 - TEST",
            "Código curso": "202",
            "Semestre": "1",
            "Grupo": "01",
            "Curso": "Test",
            "Correo Institucional": "t@ut.edu.co",
            "Docente": "T T",
        }
    ])
    result = DistanciaParser.parse(df, modalidad="DISTANCIA")
    for course in result["courses"]:
        assert "shortname" in course
        assert "fullname" in course
        assert "category_idnumber" in course
        assert "templatecourse" in course
        assert "enrolment_1" not in course, "enrolment_1 no debe enviarse a Moodle 3.9"
        assert "enrolment_1_role" not in course, "enrolment_1_role no debe enviarse a Moodle 3.9"