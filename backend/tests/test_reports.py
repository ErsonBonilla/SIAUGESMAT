"""
Pruebas unitarias para ReportService (FASE 4).

Verifica la generación de archivos CSV a partir de logs de ejecución.
"""

import csv
import os
import tempfile
import zipfile
from unittest.mock import patch

from app.core.config import settings
from app.services.reports import ReportService


def _make_log(action: str, phase: str = "2", identifier: str = "",
              detail: dict = None):
    obj = type("FakeLog", (), {})()
    obj.action = action
    obj.phase = phase
    obj.identifier = identifier
    obj.detail = detail or {}
    return obj


def _process_report_config(report_dir: str, key: str, logs: list):
    cfg = next(c for c in ReportService.REPORT_CONFIGS if c["key"] == key)
    filename = ReportService.REPORT_NAMES[key]
    rows = [cfg["extract"](log) for log in logs if cfg["match"](log)]
    ReportService._write_csv(
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
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            return list(reader)

    def test_resumen_ejecutivo(self):
        logs = [
            _make_log("course_created", detail={"reason": "new"}),
            _make_log("course_deleted", detail={"reason": "disappeared"}),
            _make_log("enrolment_ok", detail={}),
            _make_log("enrolment_failed", detail={"reason": "user_not_found"}),
        ]
        ReportService._write_resumen_ejecutivo(self.tmpdir, logs)
        data = self._read_csv("01_resumen_ejecutivo.csv")
        assert data is not None
        assert len(data) > 1  # header + rows

    def test_inc_usuarios_inactivos(self):
        logs = [
            _make_log("enrolment_failed", identifier="a@b.com",
                      detail={"reason": "user_not_found", "course": "C1"}),
            _make_log("enrolment_failed", identifier="b@b.com",
                      detail={"reason": "user_inactive", "course": "C2"}),
            _make_log("enrolment_ok", identifier="c@b.com",
                      detail={"reason": "enrolled"}),
        ]
        _process_report_config(self.tmpdir, "inc_usuarios_inactivos", logs)
        data = self._read_csv("02_inc_usuarios_inactivos.csv")
        assert data is not None
        assert len(data) == 3  # header + 2 rows

    def test_audit_cursos_creados(self):
        logs = [
            _make_log("course_created", identifier="C1",
                      detail={"reason": "new", "professor": "p1"}),
            _make_log("course_created_with_template", identifier="C2",
                      detail={"reason": "same_professor_new_group",
                              "professor": "p1"}),
        ]
        _process_report_config(self.tmpdir, "audit_cursos_creados", logs)
        data = self._read_csv("07_audit_cursos_creados.csv")
        assert data is not None
        assert len(data) == 3  # header + 2 rows
        assert data[1][0] == "C1"


class TestReportServiceIntegration:

    def test_generate_all_creates_csvs(self):
        logs = [
            _make_log("course_created", phase="2", identifier="C1",
                      detail={"reason": "new", "professor": "p1"}),
            _make_log("enrolment_ok", phase="3", identifier="user1",
                      detail={"course": "C1"}),
        ]

        class FakeExec:
            id = 999
            semester = "2025B"
            filename = "test.xlsx"
            duration_seconds = 120.5
            errors_count = 0
            moodle_version = "3.9"
            modalidad = "DISTANCIA"
            metrics = {
                "categories_created": 1, "courses_created": 1,
                "courses_deleted": 0, "courses_activated": 0,
                "users_created": 0, "enrolments": 1,
                "enrolment_errors": 0, "alerts": 0,
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
            with patch.object(settings, "REPORT_DIR", tmpdir), \
                 patch.object(ReportService, "_write_audit_errores"), \
                 patch("app.services.charts.ChartService.generate_all"):
                report_dir = ReportService.generate_all(999, FakeDB())

            assert os.path.exists(report_dir)
            for key, filename in ReportService.REPORT_NAMES.items():
                if key == "audit_errores":
                    continue  # mockeado en este test
                path = os.path.join(report_dir, filename)
                assert os.path.exists(path), f"Falta: {filename}"

            zip_path = report_dir + ".zip"
            assert os.path.exists(zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                assert any(n.endswith(".csv") for n in names)
