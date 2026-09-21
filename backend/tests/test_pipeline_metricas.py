"""Pruebas del núcleo puro de métricas y semáforo."""

import pytest

from app.pipeline.metricas import (
    calcular_tasa_error,
    color_semaforo,
    mensaje_semaforo,
)

THRESHOLDS = {
    "error_rate_yellow": 1.0,
    "error_rate_red": 5.0,
    "max_duration_yellow": 3600.0,
    "max_duration_red": 7200.0,
}


class TestCalculateErrorRate:
    def test_uses_total_operations(self):
        assert calcular_tasa_error({"total_operations": 320}, 2) == pytest.approx(0.625)

    def test_falls_back_to_sum_of_created(self):
        metrics = {"courses_created": 150, "users_created": 20, "enrolments": 150}
        assert calcular_tasa_error(metrics, 2) == pytest.approx(2.0 / 320 * 100)

    def test_zero_total_returns_zero(self):
        assert calcular_tasa_error({}, 5) == 0.0

    def test_none_metrics(self):
        assert calcular_tasa_error(None, None) == 0.0

    def test_zero_errors_returns_zero(self):
        assert calcular_tasa_error({"total_operations": 100}, 0) == 0.0


class TestSemaphoreColor:
    def test_green_when_below_all_thresholds(self):
        assert color_semaforo(0.5, 100, THRESHOLDS) == "green"

    def test_yellow_on_error_rate(self):
        assert color_semaforo(3.0, 100, THRESHOLDS) == "yellow"

    def test_yellow_on_duration(self):
        assert color_semaforo(0.5, 4000, THRESHOLDS) == "yellow"

    def test_red_on_error_rate(self):
        assert color_semaforo(6.0, 100, THRESHOLDS) == "red"

    def test_red_on_duration(self):
        assert color_semaforo(0.5, 8000, THRESHOLDS) == "red"

    def test_boundary_values(self):
        assert color_semaforo(5.0, 100, THRESHOLDS) == "red"
        assert color_semaforo(1.0, 100, THRESHOLDS) == "yellow"


class TestSemaphoreMessage:
    def test_messages(self):
        assert mensaje_semaforo("green") == "Proceso exitoso."
        assert mensaje_semaforo("yellow") == "Se superaron umbrales de advertencia."
        assert mensaje_semaforo("red") == "Se superaron umbrales críticos de error o duración."
