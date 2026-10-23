"""
Pruebas unitarias para ReportService (FASE 4).

Verifica la generación de archivos CSV a partir de logs de ejecución.
"""

import csv
import os
import tempfile
import zipfile
from typing import ClassVar
from unittest.mock import patch

from app.core.config import settings
from app.services.reportes import ServicioReportes
from app.services.utilidades_reportes import escribir_csv, obtener_ruta_csv


def _make_log(accion: str, fase: str = "2", identificador: str = "", detalle: dict = None):
    obj = type("FakeLog", (), {})()
    obj.accion = accion
    obj.fase = fase
    obj.identificador = identificador
    obj.detalle = detalle or {}
    return obj


def _process_report_config(report_dir: str, key: str, logs: list):
    cfg = next(c for c in ServicioReportes.REPORT_CONFIGS if c["key"] == key)
    filename = ServicioReportes.REPORT_NAMES[key]
    rows = [cfg["extract"](log) for log in logs if cfg["match"](log)]
    escribir_csv(
        os.path.join(report_dir, filename),
        cfg["headers"],
        rows,
    )


class TestReportGeneration:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _read_csv(self, filename: str) -> list:
        path = os.path.join(self.tmpdir, filename)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            return list(reader)

    def test_resumen_ejecutivo(self):
        logs = [
            _make_log("course_created", detalle={"reason": "new"}),
            _make_log("course_deleted", detalle={"reason": "disappeared"}),
            _make_log("enrolment_ok", detalle={}),
            _make_log("enrolment_failed", detalle={"reason": "user_not_found"}),
        ]
        ServicioReportes._escribir_resumen_ejecutivo(self.tmpdir, logs)
        data = self._read_csv("01_resumen_ejecutivo.csv")
        assert data is not None
        assert len(data) > 1  # header + rows

    def test_resumen_ejecutivo_incluye_ejemplos_de_plantillas(self):
        fake = type(
            "FakeExec",
            (),
            {
                "semestre": "2026B",
                "nombre_archivo": "carga.xlsx",
                "duracion_segundos": 10.0,
                "version_moodle": "3.9",
                "modalidad": "DISTANCIA",
                "conteo_errores": 0,
                "metricas": {
                    "templates_missing": 2,
                    "templates_missing_examples": [
                        "PORTAFOLIO_0105_sI_101",
                        "PORTAFOLIO_0105_sI_102",
                    ],
                },
            },
        )()
        ServicioReportes._escribir_resumen_ejecutivo(self.tmpdir, [], fake)
        data = self._read_csv("01_resumen_ejecutivo.csv")
        row = next(r for r in data if r[0] == "Plantillas faltantes (ejemplos)")
        assert "PORTAFOLIO_0105_sI_101" in row[1]

    def test_inc_usuarios_inactivos(self):
        logs = [
            _make_log(
                "enrolment_failed",
                identificador="a@b.com",
                detalle={"reason": "user_not_found", "course": "C1"},
            ),
            _make_log(
                "enrolment_failed",
                identificador="b@b.com",
                detalle={"reason": "user_inactive", "course": "C2"},
            ),
            _make_log("enrolment_ok", identificador="c@b.com", detalle={"reason": "enrolled"}),
        ]
        _process_report_config(self.tmpdir, "inc_usuarios_inactivos", logs)
        data = self._read_csv("02_inc_usuarios_inactivos.csv")
        assert data is not None
        assert len(data) == 3  # header + 2 rows

    def test_audit_cursos_creados(self):
        logs = [
            _make_log(
                "course_created", identificador="C1", detalle={"reason": "new", "professor": "p1"}
            ),
            _make_log(
                "course_created_with_template",
                identificador="C2",
                detalle={"reason": "same_professor_new_group", "professor": "p1"},
            ),
        ]
        _process_report_config(self.tmpdir, "audit_cursos_creados", logs)
        data = self._read_csv("07_audit_cursos_creados.csv")
        assert data is not None
        assert len(data) == 3  # header + 2 rows
        assert data[1][0] == "C1"

    def test_audit_conflictos_identidad(self):
        logs = [
            _make_log(
                "user_identity_conflict",
                fase="1",
                identificador="mbermudez",
                detalle={
                    "email": "mbermudez@univ.edu",
                    "etl_fullname": "María Bermúdez",
                    "moodle_fullname": "Juan Bermúdez",
                    "matched_by": "username",
                },
            ),
            _make_log(
                "user_resolved", fase="1", identificador="otro", detalle={"email": "otro@univ.edu"}
            ),
        ]
        _process_report_config(self.tmpdir, "audit_conflictos_identidad", logs)
        data = self._read_csv("14_audit_conflictos_identidad.csv")
        assert data is not None
        assert len(data) == 2  # header + 1 row
        assert data[1][0] == "mbermudez"
        assert data[1][1] == "mbermudez@univ.edu"
        assert data[1][4] == "username"

    def test_audit_plan_acciones(self):
        logs = [
            _make_log(
                "planned_course_created",
                identificador="C1",
                detalle={"reason": "new", "professor": "p1"},
            ),
            _make_log(
                "planned_course_deleted",
                identificador="C2",
                detalle={"reason": "disappeared", "age_seconds": 864000},
            ),
            _make_log("course_created", identificador="C3", detalle={"reason": "new"}),
        ]
        _process_report_config(self.tmpdir, "audit_plan_acciones", logs)
        data = self._read_csv("15_audit_plan_acciones.csv")
        assert data is not None
        assert len(data) == 3  # header + 2 rows
        assert data[1][0] == "C1"
        assert data[1][1] == "course_created"
        assert data[1][2] == "new"
        assert data[1][3] == "p1"
        assert data[2][0] == "C2"
        assert data[2][1] == "course_deleted"
        assert data[2][4] == "10.0"

    def test_usuarios_creados_manual(self):
        logs = [
            _make_log(
                "user_created_createpassword",
                fase="4",
                identificador="maria.perez",
                detalle={"firstname": "María", "lastname": "Pérez", "email": "mperez@ut.edu.co"},
            ),
            _make_log(
                "user_resolved",
                fase="1",
                identificador="doc.existente",
                detalle={"firstname": "Juan", "lastname": "Díaz", "email": "jdiaz@ut.edu.co"},
            ),
        ]
        _process_report_config(self.tmpdir, "usuarios_creados_manual", logs)
        data = self._read_csv("17_usuarios_creados_manual.csv")
        assert data is not None
        assert len(data) == 2  # header + 1 row (solo creados, no resueltos)
        assert data[0] == [
            "Username",
            "Correo institucional",
            "Nombre y Apellidos",
            "Base de datos",
        ]
        assert data[1][0] == "maria.perez"
        assert data[1][1] == "mperez@ut.edu.co"
        assert data[1][2] == "María Pérez"
        assert data[1][3] == "Manual"


class TestReportServiceIntegration:
    def test_generate_all_creates_csvs(self):
        logs = [
            _make_log(
                "course_created",
                fase="2",
                identificador="C1",
                detalle={"reason": "new", "professor": "p1"},
            ),
            _make_log("enrolment_ok", fase="3", identificador="user1", detalle={"course": "C1"}),
        ]

        class FakeExec:
            id = 999
            semestre = "2025B"
            nombre_archivo = "test.xlsx"
            duracion_segundos = 120.5
            conteo_errores = 0
            version_moodle = "3.9"
            modalidad = "DISTANCIA"
            metricas: ClassVar[dict] = {
                "categories_created": 1,
                "courses_created": 1,
                "courses_deleted": 0,
                "courses_activated": 0,
                "users_created": 0,
                "enrolments": 1,
                "enrolment_errors": 0,
                "alerts": 0,
            }

        class FakeFiltered:
            @staticmethod
            def all():
                return logs

            @staticmethod
            def first():
                return FakeExec()

        class FakeQuery:
            @staticmethod
            def filter(*args):
                return FakeFiltered()

        class FakeDB:
            @staticmethod
            def query(*args):
                return FakeQuery()

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(settings, "REPORT_DIR", tmpdir),
                patch.object(ServicioReportes, "_escribir_auditoria_errores"),
                patch("app.services.graficos.ServicioGraficos.generar_todos"),
            ):
                report_dir = ServicioReportes.generar_todos(999, FakeDB())

            assert os.path.exists(report_dir)
            expected = {"audit_cursos_creados", "audit_matriculas", "resumen_ejecutivo"}
            for key, filename in ServicioReportes.REPORT_NAMES.items():
                if key == "audit_errores":
                    continue
                path = os.path.join(report_dir, filename)
                if key in expected:
                    assert os.path.exists(path), f"Falta: {filename}"
                else:
                    assert not os.path.exists(path), f"Sobró: {filename}"

            zip_path = report_dir + ".zip"
            assert os.path.exists(zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert any(n.endswith(".csv") for n in names)


class TestObtenerRutaCsv:
    def test_nombre_valido(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "resumen.csv"), "w") as f:
                f.write("a,b\n1,2\n")
            assert obtener_ruta_csv(tmpdir, "resumen") == os.path.join(tmpdir, "resumen.csv")

    def test_inexistente(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert obtener_ruta_csv(tmpdir, "no_existe") is None

    def test_rechaza_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert obtener_ruta_csv(tmpdir, "../secreto") is None
            assert obtener_ruta_csv(tmpdir, "..\\secreto") is None
            assert obtener_ruta_csv(tmpdir, "..") is None

    def test_rechaza_separador_en_nombre(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assert obtener_ruta_csv(tmpdir, "sub/dir/reporte") is None
