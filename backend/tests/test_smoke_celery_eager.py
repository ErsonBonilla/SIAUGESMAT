"""
Smoke de dispatch Celery en modo eager.

Valida que `.delay()` de las tareas principales despacha de verdad a través
del registro de Celery (no una llamada directa), ejecutándose inline en modo
eager. Complementa `test_contrato_celery.py` (consistencia de nombres).
"""

from unittest.mock import MagicMock, patch

import pytest

from app.celery_app import celery_app
from app.workers.tareas import procesar_archivo_etl
from app.workers.tareas_consultas import ejecutar_consulta
from app.workers.tareas_operaciones import procesar_lote_operacion


@pytest.fixture(autouse=True)
def modo_eager():
    prev = celery_app.conf.task_always_eager
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = prev


def test_dispatch_eager_procesar_archivo_etl():
    with (
        patch("app.workers.tareas.SessionLocal") as mock_sl,
        patch("app.workers.tareas.obtener_ejecucion", return_value=None),
    ):
        mock_db = MagicMock()
        mock_sl.return_value = mock_db
        result = procesar_archivo_etl.delay(1, "/tmp/x.xlsx", "2025A")
        assert result.successful()
        mock_db.close.assert_called_once()


def test_dispatch_eager_ejecutar_consulta():
    with (
        patch("app.workers.tareas_consultas.SessionLocal") as mock_sl,
        patch("app.workers.tareas_consultas.marcar_consulta_en_ejecucion"),
        patch("app.workers.tareas_consultas.obtener_consulta", return_value=None),
    ):
        mock_sl.return_value = MagicMock()
        result = ejecutar_consulta.delay("task-1")
        assert result.successful()


def test_dispatch_eager_procesar_lote_operacion():
    with (
        patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
        patch("app.workers.tareas_operaciones.obtener_lote", return_value=None),
    ):
        mock_sl.return_value = MagicMock()
        result = procesar_lote_operacion.delay("batch-1")
        assert result.successful()
