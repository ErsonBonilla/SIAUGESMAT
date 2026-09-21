"""
Consistencia de nombres de tareas Celery.

Los ``name=`` de las tareas son cadenas opacas que se preservaron en inglés
(contrato), y todos los envíos por string (`send_task`, `beat_schedule`) deben
referenciar tareas realmente registradas. Estos tests detectan un `name=`
renombrado sin actualizar a la vez todas las referencias.
"""

import pytest

from app.celery_app import celery_app
from app.workers import tareas, tareas_consultas, tareas_limpieza, tareas_operaciones
from app.workers.phases import comunes, fase3_estructura, orquestador, tarea_item

# name= registrados (opacos, preservados por diseño)
NOMBRES_ESPERADOS = {
    "app.workers.tasks.process_etl_file",
    "app.workers.phases.item_task.process_etl_item",
    "app.workers.phases.common.on_phase_items_done",
    "app.workers.phases.common.on_users_done",
    "app.workers.phases.orchestrator.process_etl_phase",
    "app.workers.cleanup_tasks.cleanup_pending_executions",
    "app.workers.cleanup_tasks.cleanup_stuck_executions",
    "app.workers.cleanup_tasks.recover_stuck_phase",
    "app.workers.operations_tasks.process_operation_batch",
    "app.workers.query_tasks.execute_query",
    "app.workers.phases.phase3_structure.on_delete_items_done",
}


def _tareas_registradas() -> set[str]:
    return set(celery_app.tasks.keys())


def test_todas_las_tareas_registradas():
    registradas = _tareas_registradas()
    faltantes = NOMBRES_ESPERADOS - registradas
    assert not faltantes, f"tareas sin registrar: {faltantes}"


def test_beat_schedule_referencia_tareas_registradas():
    registradas = _tareas_registradas()
    schedule = celery_app.conf.get("beat_schedule") or {}
    for nombre, entrada in schedule.items():
        task = entrada["task"]
        assert task in registradas, f"beat_schedule {nombre!r} apunta a tarea no registrada: {task}"


def test_send_task_de_comunes_referencia_tarea_registrada():
    """El salto FASE 3 -> FASE 4 usa send_task por string."""
    registradas = _tareas_registradas()
    destino = "app.workers.phases.orchestrator.process_etl_phase"
    assert destino in registradas


def test_imports_de_celery_son_modulos_espanoles():
    imports = celery_app.conf.get("imports")
    assert "app.workers.tareas" in imports
    assert "app.workers.phases.orquestador" in imports
    assert "app.workers.tareas_consultas" in imports
    assert "app.workers.tareas_operaciones" in imports
    assert "app.workers.tareas_limpieza" in imports
    # Ningún import debe apuntar a módulos ingleses inexistentes
    for modulo in imports:
        __import__(modulo)


@pytest.mark.parametrize(
    "modulo",
    [
        tareas,
        tareas_consultas,
        tareas_operaciones,
        tareas_limpieza,
        comunes,
        orquestador,
        tarea_item,
        fase3_estructura,
    ],
)
def test_modulos_de_tareas_importan_sin_error(modulo):
    assert modulo is not None
