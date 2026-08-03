"""Pruebas del núcleo puro de métricas y semáforo."""
import pytest

from app.pipeline.metrics import (
    calculate_error_rate,
    semaphore_color,
    semaphore_message,
)

THRESHOLDS = {
    "error_rate_yellow": 1.0,
    "error_rate_red": 5.0,
    "max_duration_yellow": 3600.0,
    "max_duration_red": 7200.0,
}


class TestCalculateErrorRate:
    def test_uses_total_operations(self):
        assert calculate_error_rate({"total_operations": 320}, 2) == pytest.approx(0.625)

    def test_falls_back_to_sum_of_created(self):
        metrics = {"courses_created": 150, "users_created": 20, "enrolments": 150}
        assert calculate_error_rate(metrics, 2) == pytest.approx(2.0 / 320 * 100)

    def test_zero_total_returns_zero(self):
        assert calculate_error_rate({}, 5) == 0.0

    def test_none_metrics(self):
        assert calculate_error_rate(None, None) == 0.0

    def test_zero_errors_returns_zero(self):
        assert calculate_error_rate({"total_operations": 100}, 0) == 0.0


class TestSemaphoreColor:
    def test_green_when_below_all_thresholds(self):
        assert semaphore_color(0.5, 100, THRESHOLDS) == "green"

    def test_yellow_on_error_rate(self):
        assert semaphore_color(3.0, 100, THRESHOLDS) == "yellow"

    def test_yellow_on_duration(self):
        assert semaphore_color(0.5, 4000, THRESHOLDS) == "yellow"

    def test_red_on_error_rate(self):
        assert semaphore_color(6.0, 100, THRESHOLDS) == "red"

    def test_red_on_duration(self):
        assert semaphore_color(0.5, 8000, THRESHOLDS) == "red"

    def test_boundary_values(self):
        assert semaphore_color(5.0, 100, THRESHOLDS) == "red"
        assert semaphore_color(1.0, 100, THRESHOLDS) == "yellow"


class TestSemaphoreMessage:
    def test_messages(self):
        assert semaphore_message("green") == "Proceso exitoso."
        assert semaphore_message("yellow") == "Se superaron umbrales de advertencia."
        assert semaphore_message("red") == "Se superaron umbrales críticos de error o duración."
