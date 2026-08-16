"""
Pruebas unitarias para los repositorios de Execution y Logs.

Verifica que las funciones de acceso a datos (execution_repo, log_repo)
crean y actualizan correctamente las entidades en base de datos.
"""

from datetime import UTC, datetime

import pytest

from app.db.modelos import Ejecucion, RegistroEjecucion, RegistroError
from app.repositories.repositorio_ejecuciones import (
    actualizar_progreso,
    es_re_subida,
    establecer_directorio_reportes,
    marcar_completado,
    marcar_en_ejecucion,
    marcar_fallido,
    obtener_ejecucion,
)
from app.repositories.repositorio_registros import guardar_error, guardar_log


@pytest.fixture
def execution(test_db):
    ex = Ejecucion(
        nombre_archivo="test.xlsx",
        semestre="2025A",
        modo="both",
        estado="pending",
        modalidad="DISTANCIA",
        creado_en=datetime.now(UTC),
    )
    test_db.add(ex)
    test_db.commit()
    test_db.refresh(ex)
    return ex


class TestExecutionRepo:
    def test_get_execution_found(self, test_db, execution):
        ex = obtener_ejecucion(test_db, execution.id)
        assert ex is not None
        assert ex.nombre_archivo == "test.xlsx"

    def test_get_execution_not_found(self, test_db):
        assert obtener_ejecucion(test_db, 9999) is None

    def test_mark_running(self, test_db, execution):
        marcar_en_ejecucion(test_db, execution.id)
        test_db.refresh(execution)
        assert execution.estado == "running"
        assert execution.iniciado_en is not None

    def test_update_progress(self, test_db, execution):
        actualizar_progreso(test_db, execution.id, 42.0, "Creando cursos…", paso=3)
        test_db.refresh(execution)
        assert execution.fase_actual == "Creando cursos…"
        assert execution.porcentaje_progreso == 42.0
        assert execution.paso_actual == 3

    def test_update_progress_without_step(self, test_db, execution):
        actualizar_progreso(test_db, execution.id, 99.0, "Reportes generados")
        test_db.refresh(execution)
        assert execution.porcentaje_progreso == 99.0
        assert execution.fase_actual == "Reportes generados"

    def test_update_progress_not_found(self, test_db):
        actualizar_progreso(test_db, 9999, 50, "test")
        test_db.commit()

    def test_mark_completed(self, test_db, execution):
        metrics = {"categories_created": 1, "total_errors": 2}
        marcar_completado(test_db, execution.id, metrics, conteo_errores=2, duracion_segundos=3.5)
        test_db.refresh(execution)
        assert execution.estado == "completed"
        assert execution.metricas == metrics
        assert execution.conteo_errores == 2
        assert execution.duracion_segundos == 3.5
        assert execution.fase_actual == "Procesamiento completado"
        assert execution.porcentaje_progreso == 100

    def test_mark_failed(self, test_db, execution):
        marcar_fallido(test_db, execution.id, 10.0)
        test_db.refresh(execution)
        assert execution.estado == "failed"
        assert execution.completado_en is not None
        assert execution.duracion_segundos == 10.0

    def test_set_report_dir(self, test_db, execution):
        establecer_directorio_reportes(test_db, execution.id, "/reports/42/")
        test_db.refresh(execution)
        assert execution.directorio_reporte == "/reports/42/"

    def test_is_reupload_false(self, test_db, execution):
        assert es_re_subida(test_db, execution.semestre, execution.modalidad, execution.id) is False

    def test_is_reupload_true(self, test_db, execution):
        prev = Ejecucion(
            nombre_archivo="prev.xlsx",
            semestre=execution.semestre,
            modo="both",
            estado="completed",
            modalidad=execution.modalidad,
            creado_en=datetime.now(UTC),
        )
        test_db.add(prev)
        test_db.commit()
        assert es_re_subida(test_db, execution.semestre, execution.modalidad, execution.id) is True

    def test_is_reupload_ignores_failed(self, test_db, execution):
        prev = Ejecucion(
            nombre_archivo="failed.xlsx",
            semestre=execution.semestre,
            modo="both",
            estado="failed",
            modalidad=execution.modalidad,
            creado_en=datetime.now(UTC),
        )
        test_db.add(prev)
        test_db.commit()
        assert es_re_subida(test_db, execution.semestre, execution.modalidad, execution.id) is False

    def test_is_reupload_excludes_self(self, test_db, execution):
        execution.estado = "completed"
        test_db.commit()
        assert es_re_subida(test_db, execution.semestre, execution.modalidad, execution.id) is False


class TestLogRepo:
    def test_save_log(self, test_db, execution):
        guardar_log(
            test_db,
            execution.id,
            "1",
            "phase1_complete",
            identificador="test_sn",
            detalle={"k": "v"},
        )
        test_db.commit()
        logs = (
            test_db.query(RegistroEjecucion)
            .filter(RegistroEjecucion.ejecucion_id == execution.id)
            .all()
        )
        assert len(logs) == 1
        assert logs[0].fase == "1"
        assert logs[0].accion == "phase1_complete"
        assert logs[0].identificador == "test_sn"
        assert logs[0].detalle == {"k": "v"}

    def test_save_log_defaults(self, test_db, execution):
        guardar_log(test_db, execution.id, "2", "test_action")
        test_db.commit()
        log = test_db.query(RegistroEjecucion).first()
        assert log.identificador is None
        assert log.detalle == {}

    def test_save_error(self, test_db, execution):
        guardar_error(test_db, execution.id, "3", identificador="bad_course", mensaje="Fallo")
        test_db.commit()
        errors = (
            test_db.query(RegistroError).filter(RegistroError.ejecucion_id == execution.id).all()
        )
        assert len(errors) == 1
        assert errors[0].tipo == "3"
        assert errors[0].identificador == "bad_course"
        assert errors[0].mensaje == "Fallo"
