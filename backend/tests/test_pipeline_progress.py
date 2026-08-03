"""Pruebas del núcleo puro de progreso por fases."""
from app.pipeline.progress import compute_phase_progress


class TestComputePhaseProgress:
    def test_no_items_uses_fallback(self):
        assert compute_phase_progress(0, 0, 0, 0) == 34.0

    def test_phase3_in_progress_range(self):
        # 34 + (0.5 * 28) = 48
        assert compute_phase_progress(10, 5, 0, 0) == 48.0

    def test_phase3_full_range(self):
        assert compute_phase_progress(10, 0, 0, 0) == 34.0
        # Al terminar fase 3 (done == total) ya no aplica la fórmula de fase 3.
        assert compute_phase_progress(10, 10, 0, 0) == 62.0

    def test_phase4_in_progress(self):
        # Fase 3 completa, fase 4 al 50%: 65 + (0.5 * 20) = 75
        assert compute_phase_progress(10, 10, 10, 5) == 75.0

    def test_phase4_full_range(self):
        assert compute_phase_progress(10, 10, 10, 0) == 65.0
        assert compute_phase_progress(10, 10, 10, 10) == 85.0

    def test_rounds_to_one_decimal(self):
        # 34 + (1/3 * 28) = 43.333... → 43.3
        assert compute_phase_progress(3, 1, 0, 0) == 43.3

    def test_no_division_by_zero_when_totals_zero(self):
        assert compute_phase_progress(0, 0, 0, 0) == 34.0
