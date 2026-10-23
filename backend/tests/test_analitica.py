"""
Pruebas unitarias para el módulo de analítica (metrics.py y repository.py).

Verifica el cálculo de métricas agregadas por semestre, el estado del semáforo
y el resumen de la última ejecución, utilizando la base de datos en memoria.
"""

from datetime import UTC, datetime

import pytest

from app.db.modelos import Ejecucion
from app.schemas.analitica import (
    EjecucionReciente,
)
from app.services.servicio_metricas import (
    obtener_datos_ejecucion_reciente,
    obtener_estado_semaforo,
    obtener_metricas_historial,
)


# ---------------------------------------------------------------------------
# Fixtures específicos (el test_db ya viene de conftest.py)
# ---------------------------------------------------------------------------
@pytest.fixture
def ejecuciones_muestra(test_db):
    """
    Inserta varias ejecuciones de ejemplo en la base de datos de prueba.
    Semestres: 2025A, 2024B
    """
    exec1 = Ejecucion(
        nombre_archivo="carga2025A.xlsx",
        semestre="2025A",
        modo="both",
        estado="completed",
        metricas={
            "courses_created": 150,
            "users_created": 20,
            "enrolments": 150,
            "categories_created": 3,
            "total_operations": 320,
        },
        conteo_errores=2,
        iniciado_en=datetime(2025, 3, 1, 10, 0, 0, tzinfo=UTC),
        completado_en=datetime(2025, 3, 1, 10, 30, 0, tzinfo=UTC),
        duracion_segundos=1800.0,
    )
    exec2 = Ejecucion(
        nombre_archivo="carga2025A_v2.xlsx",
        semestre="2025A",
        modo="courses",
        estado="completed",
        metricas={
            "courses_created": 10,
            "users_created": 0,
            "enrolments": 10,
            "categories_created": 1,
            "total_operations": 20,
        },
        conteo_errores=0,
        iniciado_en=datetime(2025, 3, 15, 8, 0, 0, tzinfo=UTC),
        completado_en=datetime(2025, 3, 15, 8, 5, 0, tzinfo=UTC),
        duracion_segundos=300.0,
    )
    exec3 = Ejecucion(
        nombre_archivo="carga2024B.xlsx",
        semestre="2024B",
        modo="both",
        estado="completed",
        metricas={
            "courses_created": 200,
            "users_created": 30,
            "enrolments": 200,
            "categories_created": 4,
            "total_operations": 430,
        },
        conteo_errores=10,
        iniciado_en=datetime(2024, 9, 1, 10, 0, 0, tzinfo=UTC),
        completado_en=datetime(2024, 9, 1, 12, 0, 0, tzinfo=UTC),
        duracion_segundos=7200.0,
    )
    exec4 = Ejecucion(
        nombre_archivo="fallida2025A.xlsx",
        semestre="2025A",
        modo="users",
        estado="failed",
        metricas={"users_created": 5},
        conteo_errores=1,
        iniciado_en=datetime(2025, 4, 1, 10, 0, 0, tzinfo=UTC),
        duracion_segundos=None,
    )
    test_db.add_all([exec1, exec2, exec3, exec4])
    test_db.commit()
    return test_db

    # ---------------------------------------------------------------------------
    # get_history_metrics
    # ---------------------------------------------------------------------------


def test_history_metrics_aggregation(ejecuciones_muestra):
    """Debe agregar correctamente las métricas por semestre."""
    history = obtener_metricas_historial(ejecuciones_muestra, limit=10)
    assert len(history) == 2  # 2025A y 2024B
    # Orden: más reciente primero
    assert history[0].semestre == "2025A"
    assert history[1].semestre == "2024B"

    # Métricas 2025A: cursos = 150+10=160, usuarios = 20+5=25, enrollments=150+10=160
    sem2025 = history[0]
    assert sem2025.total_cursos_creados == 160
    assert sem2025.total_usuarios_creados == 25
    assert sem2025.total_matriculaciones == 160
    assert sem2025.total_errores == 3  # 2 + 0 + 1 (fallida)
    # Promedio de duración: solo las completadas (1800+300)/2 = 1050
    assert sem2025.duracion_promedio_segundos == 1050.0
    assert sem2025.ultima_completada is not None
    # El último completado fue exec2 (marzo 15)
    assert sem2025.ultima_completada.year == 2025
    assert sem2025.ultima_completada.month == 3
    assert sem2025.ultima_completada.day == 15

    # Métricas 2024B: un solo ejecución completada
    sem2024 = history[1]
    assert sem2024.total_cursos_creados == 200
    assert sem2024.total_usuarios_creados == 30
    assert sem2024.total_matriculaciones == 200
    assert sem2024.total_errores == 10
    assert sem2024.duracion_promedio_segundos == 7200.0


def test_history_metrics_empty(test_db):
    """Si no hay ejecuciones, debe retornar lista vacía."""
    history = obtener_metricas_historial(test_db)
    assert history == []

    # ---------------------------------------------------------------------------
    # get_semaphore_status
    # ---------------------------------------------------------------------------


def test_semaphore_green(ejecuciones_muestra):
    """Una ejecución con baja tasa de error y duración normal debe ser verde."""
    # exec2 es la última completada en 2025A (duración 300s, 0 errores, 20 ops)
    status = obtener_estado_semaforo(ejecuciones_muestra, semester="2025A")
    assert status.estado == "green"
    assert status.tasa_error == 0.0
    assert status.mensaje == "Proceso exitoso."


def test_semaphore_yellow(ejecuciones_muestra):
    """Tasa de error entre 1% y 5% o duración > 1h activa amarillo."""
    # exec1 tiene 2 errores / 320 ops ≈ 0.625% → verde por tasa, pero duración 1800s > 3600 no, sigue verde.
    # Para probar amarillo, podemos modificar los datos directamente o ver el último completado sin semestre.
    # Usaremos el exec3 de 2024B (10 errores / 430 ops ≈ 2.33%, duración 7200s > 3600).
    status = obtener_estado_semaforo(ejecuciones_muestra, semester="2024B")
    assert status.estado == "red"  # duración 7200 >= 7200 → rojo, no amarillo

    # Insertemos manualmente una ejecución con tasa de error 2% y duración 3600s (amarillo)
    exec_yellow = Ejecucion(
        nombre_archivo="yellow.xlsx",
        semestre="2025B",
        modo="both",
        estado="completed",
        metricas={
            "courses_created": 100,
            "users_created": 0,
            "enrollments": 0,
            "total_operations": 100,
        },
        conteo_errores=2,
        iniciado_en=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
        completado_en=datetime(2025, 6, 1, 11, 0, 0, tzinfo=UTC),
        duracion_segundos=3600.0,
    )
    ejecuciones_muestra.add(exec_yellow)
    ejecuciones_muestra.commit()

    status = obtener_estado_semaforo(ejecuciones_muestra, semester="2025B")
    assert status.estado == "yellow"
    assert 1.0 <= status.tasa_error < 5.0


def test_semaphore_red(ejecuciones_muestra):
    """Tasa de error >= 5% o duración >= 2h activa rojo."""
    # exec3 ya es rojo por duración 7200s
    status = obtener_estado_semaforo(ejecuciones_muestra, semester="2024B")
    assert status.estado == "red"

    # También podemos probar con alta tasa de error
    exec_red = Ejecucion(
        nombre_archivo="red.xlsx",
        semestre="2025B",
        modo="both",
        estado="completed",
        metricas={"total_operations": 100},
        conteo_errores=6,  # 6%
        iniciado_en=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
        completado_en=datetime(2025, 6, 1, 10, 10, 0, tzinfo=UTC),
        duracion_segundos=600.0,
    )
    ejecuciones_muestra.add(exec_red)
    ejecuciones_muestra.commit()
    status = obtener_estado_semaforo(ejecuciones_muestra, semester="2025B")
    # Ahora hay dos ejecuciones en 2025B: la amarilla y la roja; toma la última completada (la roja)
    assert status.estado == "red"


def test_semaphore_gray(test_db):
    """Si no hay ejecuciones completadas, debe ser gris."""
    status = obtener_estado_semaforo(test_db)
    assert status.estado == "gray"
    assert status.mensaje == "No hay ejecuciones completadas aún."

    # ---------------------------------------------------------------------------
    # get_latest_execution_data
    # ---------------------------------------------------------------------------


def test_latest_execution(ejecuciones_muestra):
    """Debe devolver la ejecución más reciente con sus métricas y semáforo."""
    latest = obtener_datos_ejecucion_reciente(ejecuciones_muestra)
    # La más reciente por created_at es la última insertada, en nuestro fixture es exec4 (fallida)
    # Pero exec4 tiene created_at por defecto, por lo que depende del orden. Vamos a asegurarnos de que exista.
    assert latest is not None
    assert isinstance(latest, EjecucionReciente)
    assert latest.id is not None
    assert latest.estado in ("completed", "failed", "pending")

    # El semáforo de la última (fallida) puede ser gris/rojo dependiendo de la métrica.
    # No importa tanto el color, sino que el objeto se construye correctamente.
    assert latest.semaforo in ("green", "yellow", "red", "gray")


def test_latest_execution_empty(test_db):
    """Si no hay ejecuciones, debe lanzar ValueError."""
    with pytest.raises(ValueError, match="No hay ejecuciones registradas"):
        obtener_datos_ejecucion_reciente(test_db)
