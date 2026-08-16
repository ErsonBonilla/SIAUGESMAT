import contextlib
from unittest.mock import MagicMock, patch

import pytest

from app.workers.phases.base import ErrorMoodleSobrecargado
from app.workers.tareas import procesar_archivo_etl


class TestProcessEtlFile:
    def test_execution_not_found(self):
        with (
            patch("app.workers.tareas.SessionLocal") as mock_sl,
            patch("app.workers.tareas.obtener_ejecucion", return_value=None),
        ):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            procesar_archivo_etl(1, "/tmp/test.xlsx", "2025A")
            mock_db.close.assert_called_once()

    @pytest.mark.parametrize("status", ["cancelled", "paused", "review_required"])
    def test_execution_skipped(self, status):
        with (
            patch("app.workers.tareas.SessionLocal") as mock_sl,
            patch("app.workers.tareas.obtener_ejecucion") as mock_get_ex,
        ):
            mock_ex = MagicMock()
            mock_ex.estado = status
            mock_get_ex.return_value = mock_ex
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            procesar_archivo_etl(1, "/tmp/test.xlsx", "2025A")
            mock_db.close.assert_called_once()

    @patch("app.workers.tareas.procesar_fase_etl.delay")
    @patch("app.workers.tareas.ejecutar_moodle_async")
    @patch("app.workers.tareas.IntegracionMoodle")
    @patch("app.workers.tareas.obtener_servicio_moodle")
    @patch("app.workers.tareas.ServicioETL")
    @patch("app.workers.tareas.marcar_en_ejecucion")
    def test_happy_path(
        self, mock_mark, mock_etl, mock_get_ms, mock_integ, mock_ejecutar_async, mock_delay
    ):
        mock_etl.procesar.return_value = {"courses": [], "users": []}
        mock_ms = MagicMock()
        mock_get_ms.return_value = mock_ms
        mock_ejecutar_async.return_value = {"courses_created": 1}
        with (
            patch("app.workers.tareas.SessionLocal") as mock_sl,
            patch("app.workers.tareas.obtener_ejecucion") as mock_get_ex,
            patch("app.workers.tareas.obtener_checkpoint") as mock_get_cp,
        ):
            mock_ex = MagicMock()
            mock_ex.estado = "running"
            mock_ex.modalidad = "DISTANCIA"
            mock_ex.modo = "both"
            mock_get_ex.return_value = mock_ex
            mock_get_cp.return_value = {"1": {}}
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            procesar_archivo_etl(1, "/tmp/test.xlsx", "2025A")
            mock_mark.assert_called_once()
            mock_etl.procesar.assert_called_once()
            mock_get_ms.assert_called_once_with("DISTANCIA")
            mock_integ.assert_called_once_with(mock_ms)
            mock_delay.assert_called_once_with(1, "3")

    def test_moodle_overloaded_re_raised(self):
        with (
            patch("app.workers.tareas.SessionLocal") as mock_sl,
            patch("app.workers.tareas.obtener_ejecucion") as mock_get_ex,
            patch("app.workers.tareas.marcar_en_ejecucion"),
            patch("app.workers.tareas.marcar_fallido") as mock_fail,
            patch(
                "app.workers.tareas.ServicioETL.procesar",
                side_effect=ErrorMoodleSobrecargado("overloaded"),
            ),
        ):
            mock_ex = MagicMock()
            mock_ex.estado = "running"
            mock_get_ex.return_value = mock_ex
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            with contextlib.suppress(Exception):
                procesar_archivo_etl(1, "/tmp/test.xlsx", "2025A")
            mock_fail.assert_not_called()
            mock_db.close.assert_called_once()

    @patch("app.workers.tareas.marcar_fallido")
    @patch("app.workers.tareas.guardar_error")
    def test_critical_error_calls_mark_failed(self, mock_save, mock_fail):
        with (
            patch("app.workers.tareas.SessionLocal") as mock_sl,
            patch("app.workers.tareas.obtener_ejecucion") as mock_get_ex,
            patch("app.workers.tareas.marcar_en_ejecucion"),
            patch("app.workers.tareas.ServicioETL.procesar", side_effect=ValueError("bad data")),
        ):
            mock_ex = MagicMock()
            mock_ex.estado = "running"
            mock_get_ex.return_value = mock_ex
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            procesar_archivo_etl(1, "/tmp/test.xlsx", "2025A")
            mock_save.assert_called_once()
            mock_fail.assert_called_once()
            mock_db.close.assert_called_once()
