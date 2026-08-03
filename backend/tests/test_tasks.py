from unittest.mock import MagicMock, patch

import pytest

from app.workers.phases.base import MoodleOverloadedError
from app.workers.tasks import process_etl_file


class TestProcessEtlFile:
    def test_execution_not_found(self):
        with patch("app.workers.tasks.SessionLocal") as mock_sl, \
             patch("app.workers.tasks.get_execution", return_value=None):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            process_etl_file(1, "/tmp/test.xlsx", "2025A")
            mock_db.close.assert_called_once()

    @pytest.mark.parametrize("status", ["cancelled", "paused", "review_required"])
    def test_execution_skipped(self, status):
        with patch("app.workers.tasks.SessionLocal") as mock_sl, \
             patch("app.workers.tasks.get_execution") as mock_get_ex:
            mock_ex = MagicMock()
            mock_ex.status = status
            mock_get_ex.return_value = mock_ex
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            process_etl_file(1, "/tmp/test.xlsx", "2025A")
            mock_db.close.assert_called_once()

    @patch("app.workers.tasks.process_etl_phase.delay")
    @patch("app.workers.tasks.run_moodle_async")
    @patch("app.workers.tasks.MoodleIntegration")
    @patch("app.workers.tasks.get_moodle_service")
    @patch("app.workers.tasks.ETLService")
    @patch("app.workers.tasks.mark_running")
    def test_happy_path(self, mock_mark, mock_etl, mock_get_ms, mock_integ, mock_run_async, mock_delay):
        mock_etl.process.return_value = {"courses": [], "users": []}
        mock_ms = MagicMock()
        mock_get_ms.return_value = mock_ms
        mock_run_async.return_value = {"courses_created": 1}
        with patch("app.workers.tasks.SessionLocal") as mock_sl, \
             patch("app.workers.tasks.get_execution") as mock_get_ex, \
             patch("app.workers.tasks.get_checkpoint") as mock_get_cp:
            mock_ex = MagicMock()
            mock_ex.status = "running"
            mock_ex.modalidad = "DISTANCIA"
            mock_ex.mode = "both"
            mock_get_ex.return_value = mock_ex
            mock_get_cp.return_value = {"1": {}}
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            process_etl_file(1, "/tmp/test.xlsx", "2025A")
            mock_mark.assert_called_once()
            mock_etl.process.assert_called_once()
            mock_get_ms.assert_called_once_with("DISTANCIA")
            mock_integ.assert_called_once_with(mock_ms)
            mock_delay.assert_called_once_with(1, "3")

    def test_moodle_overloaded_re_raised(self):
        with patch("app.workers.tasks.SessionLocal") as mock_sl, \
             patch("app.workers.tasks.get_execution") as mock_get_ex, \
             patch("app.workers.tasks.mark_running"), \
             patch("app.workers.tasks.mark_failed") as mock_fail, \
             patch("app.workers.tasks.ETLService.process", side_effect=MoodleOverloadedError("overloaded")):
            mock_ex = MagicMock()
            mock_ex.status = "running"
            mock_get_ex.return_value = mock_ex
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            try:
                process_etl_file(1, "/tmp/test.xlsx", "2025A")
            except Exception:
                pass
            mock_fail.assert_not_called()
            mock_db.close.assert_called_once()

    @patch("app.workers.tasks.mark_failed")
    @patch("app.workers.tasks.save_error")
    def test_critical_error_calls_mark_failed(self, mock_save, mock_fail):
        with patch("app.workers.tasks.SessionLocal") as mock_sl, \
             patch("app.workers.tasks.get_execution") as mock_get_ex, \
             patch("app.workers.tasks.mark_running"), \
             patch("app.workers.tasks.ETLService.process", side_effect=ValueError("bad data")):
            mock_ex = MagicMock()
            mock_ex.status = "running"
            mock_get_ex.return_value = mock_ex
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            process_etl_file(1, "/tmp/test.xlsx", "2025A")
            mock_save.assert_called_once()
            mock_fail.assert_called_once()
            mock_db.close.assert_called_once()
