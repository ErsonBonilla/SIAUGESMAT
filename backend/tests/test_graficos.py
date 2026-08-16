import os
import tempfile
from typing import ClassVar

from app.services.graficos import ServicioGraficos


def _make_log(accion: str, fase: str = "2", identificador: str = "", detalle: dict = None):
    obj = type("FakeLog", (), {})()
    obj.accion = accion
    obj.fase = fase
    obj.identificador = identificador
    obj.detalle = detalle or {}
    return obj


class FakeExec:
    id = 1
    semestre = "2025B"
    metricas: ClassVar[dict] = {
        "categories_created": 2,
        "courses_created": 5,
        "courses_deleted": 1,
        "courses_activated": 1,
        "users_created": 3,
        "enrolments": 10,
        "enrolment_errors": 2,
        "alerts": 3,
        "total_errors": 4,
    }


class TestChartGeneration:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_generate_all_creates_png_and_html(self):
        logs = [
            _make_log(
                "course_created",
                identificador="IDE_0105_123_sI_G-A",
                detalle={"reason": "new", "professor": "p1"},
            ),
            _make_log(
                "enrolment_ok", identificador="user1", detalle={"course": "IDE_0105_123_sI_G-A"}
            ),
            _make_log(
                "enrolment_failed",
                identificador="user2",
                detalle={"course": "IDE_0105_124_sII_G-B", "reason": "user_not_found"},
            ),
        ]
        ServicioGraficos.generar_todos(FakeExec(), logs, self.tmpdir)

        for name in ServicioGraficos.CHART_NAMES:
            prefix = ServicioGraficos.CHART_NAMES[name]
            png = os.path.join(self.tmpdir, f"{prefix}.png")
            html = os.path.join(self.tmpdir, f"{prefix}.html")
            assert os.path.exists(png), f"Falta PNG: {prefix}"
            assert os.path.exists(html), f"Falta HTML: {prefix}"

    def test_resumen_ejecutivo(self):
        fig = ServicioGraficos.resumen_ejecutivo(FakeExec(), [])
        data = fig.data[0]
        assert len(data.y) == 4  # cursos, usuarios, matrículas, errores
        assert data.x[0] == 5  # courses_created

    def test_resumen_ejecutivo_json(self):
        result = ServicioGraficos.resumen_ejecutivo_json(FakeExec(), [])
        assert "traces" in result
        assert "layout" in result

    def test_tasa_exito(self):
        fig = ServicioGraficos.tasa_exito(FakeExec(), [])
        data = fig.data[0]
        assert data.values[0] == 10  # enrolments
        assert data.values[1] == 2  # enrolment_errors

    def test_tasa_exito_zero_total(self):
        exec_zero = type("FakeExecZero", (), {})()
        exec_zero.metricas = {"enrolments": 0, "enrolment_errors": 0}
        fig = ServicioGraficos.tasa_exito(exec_zero, [])
        assert fig.data[0].values[0] == 0

    def test_top_programas(self):
        logs = [
            _make_log("course_created", identificador="IDE_0105_123_sI_G-A"),
            _make_log("course_created_with_template", identificador="IDE_0105_124_sII_G-B"),
            _make_log("course_recreated", identificador="FAC_0200_100_sII_G-C"),
            _make_log("course_created", identificador="URA_0300_200_sIII_G-D"),
        ]
        fig = ServicioGraficos.top_programas(FakeExec(), logs)
        assert len(fig.data[0].y) >= 1

    def test_distribucion_usuarios(self):
        logs = [
            _make_log("user_created_createpassword", fase="3", identificador="user1"),
            _make_log("user_created_createpassword", fase="3", identificador="user2"),
            _make_log("user_resolved", fase="1", identificador="user3"),
            _make_log("user_resolved", fase="1", identificador="user4"),
            _make_log("user_resolved", fase="1", identificador="user5"),
        ]
        fig = ServicioGraficos.distribucion_usuarios(FakeExec(), logs)
        values = fig.data[0].values
        assert values[0] == 2  # nuevos
        assert values[1] == 3  # resueltos

    def test_distribucion_usuarios_empty(self):
        fig = ServicioGraficos.distribucion_usuarios(FakeExec(), [])
        assert len(fig.data) == 0  # annotation only

    def test_top_incidencias(self):
        logs = [
            _make_log("enrolment_failed", detalle={"reason": "user_not_found"}),
            _make_log("enrolment_failed", detalle={"reason": "user_inactive"}),
            _make_log("alert_disappeared_recent"),
            _make_log("duplicate_email"),
            _make_log("template_not_found"),
        ]
        fig = ServicioGraficos.top_incidencias(FakeExec(), logs)
        assert len(fig.data[0].y) >= 1

    def test_top_incidencias_empty(self):
        fig = ServicioGraficos.top_incidencias(FakeExec(), [])
        assert len(fig.data) == 0  # annotation only
