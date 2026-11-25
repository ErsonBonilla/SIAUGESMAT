"""Pruebas unitarias del núcleo puro del Observatorio IDEAD Colombia."""

from app.pipeline.catalogo_divipola import (
    normalizar_texto_geografico,
    resolver_ubicacion_cat,
)
from app.pipeline.matriculaciones import resolver_matriculaciones
from app.pipeline.observatorio import (
    construir_censo_observatorio,
    es_rol_docente_o_gestor,
)


class TestCatalogoDivipola:
    def test_resuelve_cat_ibague_a_tolima_73001(self):
        ubic = resolver_ubicacion_cat("IBAGUE", "IBA")
        assert ubic is not None
        assert ubic["dpto_code"] == "73"
        assert ubic["dpto_name"] == "TOLIMA"
        assert ubic["mpio_code"] == "73001"

    def test_resuelve_alias_uraba_a_apartado_antioquia(self):
        ubic = resolver_ubicacion_cat("URABA", "URA")
        assert ubic is not None
        assert ubic["dpto_code"] == "05"
        assert ubic["dpto_name"] == "ANTIOQUIA"
        assert ubic["mpio_code"] == "05045"

    def test_resuelve_alias_mariquita_a_san_sebastian_de_mariquita(self):
        ubic = resolver_ubicacion_cat("MARIQUITA", "MAR")
        assert ubic is not None
        assert ubic["dpto_code"] == "73"
        assert ubic["mpio_code"] == "73443"

    def test_resuelve_sedes_bogota_tunal_y_kennedy_a_11001(self):
        tunal = resolver_ubicacion_cat("TUNAL", "TUN")
        kennedy = resolver_ubicacion_cat("KENNEDY", "KEN")
        assert tunal is not None and tunal["mpio_code"] == "11001"
        assert kennedy is not None and kennedy["mpio_code"] == "11001"

    def test_retorna_none_para_cat_inexistente(self):
        assert resolver_ubicacion_cat("PLANETA_MARTE", "XXX") is None

    def test_prioriza_token_especifico_sobre_prefijo_san(self):
        ubic = resolver_ubicacion_cat("REGIONAL SAN URABA", "")
        assert ubic is not None
        assert ubic["dpto_code"] == "05"
        assert ubic["mpio_code"] == "05045"

    def test_limpia_prefijos_institucionales_anidados(self):
        assert normalizar_texto_geografico("SEDE CAT BOGOTA") == "BOGOTA"
        assert normalizar_texto_geografico("CENTRO CREAD IBAGUE") == "IBAGUE"

    def test_resolver_matriculaciones_tolera_fila_sin_username(self):
        res = resolver_matriculaciones([{"course_shortname": "C1"}], {"u1": "m_u1"})
        assert res == [{"course_shortname": "C1", "username": ""}]


class TestRolDocenteOGestor:
    def test_detecta_editingteacher_por_shortname_o_roleid(self):
        assert es_rol_docente_o_gestor({"id": 1, "roles": [{"shortname": "editingteacher"}]})
        assert es_rol_docente_o_gestor({"id": 2, "roles": [{"roleid": 3}]})
        assert es_rol_docente_o_gestor({"id": 3, "roles": [{"shortname": "teacher"}]})
        assert es_rol_docente_o_gestor({"id": 4, "roles": [{"shortname": "manager"}]})

    def test_detecta_docente_por_conjunto_respaldo(self):
        assert es_rol_docente_o_gestor({"id": 10, "username": "prof1", "roles": []}, {"10"})
        assert es_rol_docente_o_gestor({"id": 11, "username": "prof1", "roles": []}, {"prof1"})

    def test_estudiante_no_es_docente(self):
        assert not es_rol_docente_o_gestor(
            {"id": 50, "username": "est1", "roles": [{"roleid": 5, "shortname": "student"}]}
        )


class TestConstruirCensoObservatorio:
    def _categorias_base(self):
        return [
            {"id": 1, "name": "IDEAD", "idnumber": "DISTANCIA", "parent": 0},
            {"id": 10, "name": "IBAGUE", "idnumber": "IBA", "parent": 1},
            {"id": 11, "name": "INGENIERIA DE SISTEMAS", "idnumber": "IBA_0852", "parent": 10},
            {"id": 12, "name": "SEMESTRE I", "idnumber": "IBA_0852_sI", "parent": 11},
            {"id": 13, "name": "ADMINISTRACION FINANCIERA", "idnumber": "IBA_0854", "parent": 10},
            {"id": 14, "name": "SEMESTRE II", "idnumber": "IBA_0854_sII", "parent": 13},
            {"id": 20, "name": "CHAPARRAL", "idnumber": "CHA", "parent": 1},
            {"id": 21, "name": "LICENCIATURA EN PEDAGOGIA", "idnumber": "CHA_0810", "parent": 20},
            {"id": 22, "name": "SEMESTRE I", "idnumber": "CHA_0810_sI", "parent": 21},
            {"id": 30, "name": "CALI", "idnumber": "CAL", "parent": 1},
            {"id": 31, "name": "INGENIERIA DE SISTEMAS", "idnumber": "CAL_0852", "parent": 30},
            {"id": 32, "name": "SEMESTRE IV", "idnumber": "CAL_0852_sIV", "parent": 31},
        ]

    def test_filtra_cursos_ocultos_y_sin_docente_y_excluye_profesores_del_conteo(self):
        cats = self._categorias_base()
        cursos = [
            # Curso 101: visible, con docente y 2 estudiantes (est1, est2)
            {
                "id": 101,
                "shortname": "IBA_0852_sI_501101_G-1_999",
                "fullname": "MATEMATICAS I",
                "categoryid": 12,
                "visible": 1,
            },
            # Curso 102: mismo programa IBA_0852, visible, con docente y (est1 repetido, est3 nuevo)
            {
                "id": 102,
                "shortname": "IBA_0852_sI_501102_G-1_999",
                "fullname": "PROGRAMACION I",
                "categoryid": 12,
                "visible": 1,
            },
            # Curso 103: otro programa en Ibagué (IBA_0854), con 1 estudiante (est4)
            {
                "id": 103,
                "shortname": "IBA_0854_sII_601101_G-1_888",
                "fullname": "CONTABILIDAD",
                "categoryid": 14,
                "visible": 1,
            },
            # Curso 104: en Chaparral (Tolima), con 1 estudiante (est5)
            {
                "id": 104,
                "shortname": "CHA_0810_sI_701101_G-1_777",
                "fullname": "DIDACTICA",
                "categoryid": 22,
                "visible": 1,
            },
            # Curso 105: OCULTO (visible=0) en Cali -> debe ignorarse aunque tenga docente y alumnos
            {
                "id": 105,
                "shortname": "CAL_0852_sIV_504101_G-1_666",
                "fullname": "REDES OCULTO",
                "categoryid": 32,
                "visible": 0,
            },
            # Curso 106: VISIBLE pero SIN DOCENTE en Cali -> debe ignorarse
            {
                "id": 106,
                "shortname": "CAL_0852_sIV_504102_G-1_666",
                "fullname": "BASES DE DATOS HUERFANO",
                "categoryid": 32,
                "visible": 1,
            },
        ]

        docente_rol = [{"roleid": 3, "shortname": "editingteacher"}]
        estudiante_rol = [{"roleid": 5, "shortname": "student"}]

        matriculados = {
            101: [
                {"id": 1, "username": "doc_iba", "roles": docente_rol},
                {"id": 1001, "username": "est1", "roles": estudiante_rol},
                {"id": 1002, "username": "est2", "roles": estudiante_rol},
            ],
            102: [
                {"id": 1, "username": "doc_iba", "roles": docente_rol},
                {
                    "id": 1001,
                    "username": "est1",
                    "roles": estudiante_rol,
                },  # duplicado en el programa
                {"id": 1003, "username": "est3", "roles": estudiante_rol},
            ],
            103: [
                {"id": 2, "username": "doc_fin", "roles": docente_rol},
                {"id": 1004, "username": "est4", "roles": estudiante_rol},
            ],
            104: [
                {"id": 3, "username": "doc_cha", "roles": docente_rol},
                {"id": 1005, "username": "est5", "roles": estudiante_rol},
            ],
            105: [
                {"id": 4, "username": "doc_cal", "roles": docente_rol},
                {"id": 1006, "username": "est6", "roles": estudiante_rol},
            ],
            106: [
                # Solo estudiantes, ningún docente -> curso huérfano, no cuenta
                {"id": 1007, "username": "est7", "roles": estudiante_rol},
            ],
        }

        censo = construir_censo_observatorio(
            cursos=cursos,
            categorias=cats,
            matriculados_por_curso=matriculados,
            actualizado_en="2026-11-24T17:00:00Z",
        )

        # Solo Tolima debe aparecer (Cali tenía 1 curso oculto y 1 sin docente)
        assert censo["total_departments"] == 1
        assert censo["total_cats"] == 2  # Ibagué y Chaparral
        assert censo["total_programs"] == 3  # 2 en Ibagué + 1 en Chaparral
        assert censo["total_students"] == 5  # est1, est2, est3, est4, est5 (ningún docente)

        dpto = censo["departments"][0]
        assert dpto["dpto_code"] == "73"
        assert dpto["dpto_name"] == "TOLIMA"
        assert dpto["cats_count"] == 2
        assert dpto["students_count"] == 5

        by_cat = {m["cat_shortname"]: m for m in dpto["municipalities"]}
        iba = by_cat["IBA"]
        assert iba["mpio_code"] == "73001"
        assert iba["programs_count"] == 2
        assert iba["students_count"] == 4  # est1, est2, est3, est4

        progs_iba = {p["program_code"]: p for p in iba["programs"]}
        # En Sistemas (0852) est1 está en 2 cursos pero cuenta 1 sola vez -> 3 estudiantes únicos
        assert progs_iba["0852"]["students_count"] == 3
        assert progs_iba["0854"]["students_count"] == 1

        cha = by_cat["CHA"]
        assert cha["mpio_code"] == "73168"
        assert cha["programs_count"] == 1
        assert cha["programs"][0]["students_count"] == 1

    def test_retorna_censo_vacio_si_no_existe_categoria_raiz_idead(self):
        cursos = [
            {
                "id": 101,
                "shortname": "IBA_0852_sI_501101_G-1_999",
                "fullname": "MATEMATICAS I",
                "categoryid": 12,
                "visible": 1,
            }
        ]
        matriculados = {
            101: [
                {"id": 1, "username": "doc_iba", "roles": [{"roleid": 3}]},
                {"id": 1001, "username": "est1", "roles": [{"roleid": 5}]},
            ]
        }
        censo = construir_censo_observatorio(
            cursos=cursos,
            categorias=[{"id": 12, "name": "IBAGUE", "idnumber": "IBA", "parent": 0}],
            matriculados_por_curso=matriculados,
        )
        assert censo["total_students"] == 0
        assert censo["total_departments"] == 0
        assert censo["departments"] == []

    def test_excluye_cursos_y_categorias_de_otras_facultades_fuera_de_idead(self):
        cats = [
            *self._categorias_base(),
            {"id": 90, "name": "FACULTAD INGENIERIA", "idnumber": "FAC_ING", "parent": 0},
            {"id": 91, "name": "CALI", "idnumber": "CAL", "parent": 90},
        ]
        cursos = [
            # Curso bajo categoría 91 (fuera del árbol IDEAD id=1)
            {
                "id": 201,
                "shortname": "CAL_0852_sIV_504101_G-1_666",
                "fullname": "CURSO EXTERNO",
                "categoryid": 91,
                "visible": 1,
            }
        ]
        matriculados = {
            201: [
                {"id": 1, "username": "doc1", "roles": [{"roleid": 3}]},
                {"id": 1001, "username": "est1", "roles": [{"roleid": 5}]},
            ]
        }
        censo = construir_censo_observatorio(
            cursos=cursos,
            categorias=cats,
            matriculados_por_curso=matriculados,
        )
        assert censo["total_students"] == 0
        assert censo["departments"] == []
