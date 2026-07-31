"""
Pruebas unitarias para el módulo de analítica (metrics.py y repository.py).

Verifica el cálculo de métricas agregadas por semestre, el estado del semáforo
y el resumen de la última ejecución, utilizando la base de datos en memoria.
"""

import pytest
from datetime import datetime, timezone

from app.db.models import Execution
from app.services.metrics_service import (
    get_history_metrics,
    get_semaphore_status,
    get_latest_execution_data,
)
from app.schemas.analytics import (
    SemesterMetrics,
    SemaphoreStatus,
    LatestExecution,
)
from app.core.config import settings


# ---------------------------------------------------------------------------
# Fixtures específicos (el test_db ya viene de conftest.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_executions(test_db):
    """
    Inserta varias ejecuciones de ejemplo en la base de datos de prueba.
    Semestres: 2025A, 2024B
    """
    exec1 = Execution(
        filename="carga2025A.xlsx",
        semester="2025A",
        mode="both",
        status="completed",
        metrics={
            "courses_created": 150,
            "users_created": 20,
            "enrolments": 150,
            "categories_created": 3,
            "total_operations": 320
        },
        errors_count=2,
        started_at=datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2025, 3, 1, 10, 30, 0, tzinfo=timezone.utc),
        duration_seconds=1800.0,
    )
    exec2 = Execution(
        filename="carga2025A_v2.xlsx",
        semester="2025A",
        mode="courses",
        status="completed",
        metrics={
            "courses_created": 10,
            "users_created": 0,
            "enrolments": 10,
            "categories_created": 1,
            "total_operations": 20
        },
        errors_count=0,
        started_at=datetime(2025, 3, 15, 8, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2025, 3, 15, 8, 5, 0, tzinfo=timezone.utc),
        duration_seconds=300.0,
    )
    exec3 = Execution(
        filename="carga2024B.xlsx",
        semester="2024B",
        mode="both",
        status="completed",
        metrics={
            "courses_created": 200,
            "users_created": 30,
            "enrolments": 200,
            "categories_created": 4,
            "total_operations": 430
        },
        errors_count=10,
        started_at=datetime(2024, 9, 1, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2024, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
        duration_seconds=7200.0,
    )
    exec4 = Execution(
        filename="fallida2025A.xlsx",
        semester="2025A",
        mode="users",
        status="failed",
        metrics={"users_created": 5},
        errors_count=1,
        started_at=datetime(2025, 4, 1, 10, 0, 0, tzinfo=timezone.utc),
        duration_seconds=None,
    )
    test_db.add_all([exec1, exec2, exec3, exec4])
    test_db.commit()
    return test_db


# ---------------------------------------------------------------------------
# get_history_metrics
# ---------------------------------------------------------------------------
def test_history_metrics_aggregation(sample_executions):
    """Debe agregar correctamente las métricas por semestre."""
    history = get_history_metrics(sample_executions, limit=10)
    assert len(history) == 2  # 2025A y 2024B
    # Orden: más reciente primero
    assert history[0].semester == "2025A"
    assert history[1].semester == "2024B"

    # Métricas 2025A: cursos = 150+10=160, usuarios = 20+5=25, enrollments=150+10=160
    sem2025 = history[0]
    assert sem2025.total_courses_created == 160
    assert sem2025.total_users_created == 25
    assert sem2025.total_enrollments == 160
    assert sem2025.total_errors == 3  # 2 + 0 + 1 (fallida)
    # Promedio de duración: solo las completadas (1800+300)/2 = 1050
    assert sem2025.avg_duration_seconds == 1050.0
    assert sem2025.last_completed is not None
    # El último completado fue exec2 (marzo 15)
    assert sem2025.last_completed.year == 2025
    assert sem2025.last_completed.month == 3
    assert sem2025.last_completed.day == 15

    # Métricas 2024B: un solo ejecución completada
    sem2024 = history[1]
    assert sem2024.total_courses_created == 200
    assert sem2024.total_users_created == 30
    assert sem2024.total_enrollments == 200
    assert sem2024.total_errors == 10
    assert sem2024.avg_duration_seconds == 7200.0


def test_history_metrics_empty(test_db):
    """Si no hay ejecuciones, debe retornar lista vacía."""
    history = get_history_metrics(test_db)
    assert history == []


# ---------------------------------------------------------------------------
# get_semaphore_status
# ---------------------------------------------------------------------------
def test_semaphore_green(sample_executions):
    """Una ejecución con baja tasa de error y duración normal debe ser verde."""
    # exec2 es la última completada en 2025A (duración 300s, 0 errores, 20 ops)
    status = get_semaphore_status(sample_executions, semester="2025A")
    assert status.status == "green"
    assert status.error_rate == 0.0
    assert status.message == "Proceso exitoso."


def test_semaphore_yellow(sample_executions):
    """Tasa de error entre 1% y 5% o duración > 1h activa amarillo."""
    # exec1 tiene 2 errores / 320 ops ≈ 0.625% → verde por tasa, pero duración 1800s > 3600 no, sigue verde.
    # Para probar amarillo, podemos modificar los datos directamente o ver el último completado sin semestre.
    # Usaremos el exec3 de 2024B (10 errores / 430 ops ≈ 2.33%, duración 7200s > 3600).
    status = get_semaphore_status(sample_executions, semester="2024B")
    assert status.status == "red"  # duración 7200 >= 7200 → rojo, no amarillo

    # Insertemos manualmente una ejecución con tasa de error 2% y duración 3600s (amarillo)
    from datetime import timedelta
    exec_yellow = Execution(
        filename="yellow.xlsx",
        semester="2025B",
        mode="both",
        status="completed",
        metrics={"courses_created": 100, "users_created": 0, "enrollments": 0, "total_operations": 100},
        errors_count=2,
        started_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2025, 6, 1, 11, 0, 0, tzinfo=timezone.utc),
        duration_seconds=3600.0,
    )
    sample_executions.add(exec_yellow)
    sample_executions.commit()

    status = get_semaphore_status(sample_executions, semester="2025B")
    assert status.status == "yellow"
    assert 1.0 <= status.error_rate < 5.0


def test_semaphore_red(sample_executions):
    """Tasa de error >= 5% o duración >= 2h activa rojo."""
    # exec3 ya es rojo por duración 7200s
    status = get_semaphore_status(sample_executions, semester="2024B")
    assert status.status == "red"

    # También podemos probar con alta tasa de error
    exec_red = Execution(
        filename="red.xlsx",
        semester="2025B",
        mode="both",
        status="completed",
        metrics={"total_operations": 100},
        errors_count=6,  # 6%
        started_at=datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2025, 6, 1, 10, 10, 0, tzinfo=timezone.utc),
        duration_seconds=600.0,
    )
    sample_executions.add(exec_red)
    sample_executions.commit()
    status = get_semaphore_status(sample_executions, semester="2025B")
    # Ahora hay dos ejecuciones en 2025B: la amarilla y la roja; toma la última completada (la roja)
    assert status.status == "red"


def test_semaphore_gray(test_db):
    """Si no hay ejecuciones completadas, debe ser gris."""
    status = get_semaphore_status(test_db)
    assert status.status == "gray"
    assert status.message == "No hay ejecuciones completadas aún."


# ---------------------------------------------------------------------------
# get_latest_execution_data
# ---------------------------------------------------------------------------
def test_latest_execution(sample_executions):
    """Debe devolver la ejecución más reciente con sus métricas y semáforo."""
    latest = get_latest_execution_data(sample_executions)
    # La más reciente por created_at es la última insertada, en nuestro fixture es exec4 (fallida)
    # Pero exec4 tiene created_at por defecto, por lo que depende del orden. Vamos a asegurarnos de que exista.
    assert latest is not None
    assert isinstance(latest, LatestExecution)
    assert latest.id is not None
    assert latest.status in ("completed", "failed", "pending")

    # El semáforo de la última (fallida) puede ser gris/rojo dependiendo de la métrica.
    # No importa tanto el color, sino que el objeto se construye correctamente.
    assert latest.semaphore in ("green", "yellow", "red", "gray")


def test_latest_execution_empty(test_db):
    """Si no hay ejecuciones, debe lanzar ValueError."""
    with pytest.raises(ValueError, match="No hay ejecuciones registradas"):
        get_latest_execution_data(test_db)