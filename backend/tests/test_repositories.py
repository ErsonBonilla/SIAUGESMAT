"""
Pruebas unitarias para los repositorios de Execution y Logs.

Verifica que las funciones de acceso a datos (execution_repo, log_repo)
crean y actualizan correctamente las entidades en base de datos.
"""

from datetime import UTC, datetime

import pytest

from app.db.models import ErrorLog, Execution, ExecutionLog
from app.repositories.execution_repo import (
    get_execution,
    is_reupload,
    mark_completed,
    mark_failed,
    mark_running,
    set_report_dir,
    update_progress,
)
from app.repositories.log_repo import save_error, save_log


@pytest.fixture
def execution(test_db):
    ex = Execution(
        filename="test.xlsx",
        semester="2025A",
        mode="both",
        status="pending",
        modalidad="DISTANCIA",
        created_at=datetime.now(UTC),
    )
    test_db.add(ex)
    test_db.commit()
    test_db.refresh(ex)
    return ex


class TestExecutionRepo:
    def test_get_execution_found(self, test_db, execution):
        ex = get_execution(test_db, execution.id)
        assert ex is not None
        assert ex.filename == "test.xlsx"

    def test_get_execution_not_found(self, test_db):
        assert get_execution(test_db, 9999) is None

    def test_mark_running(self, test_db, execution):
        mark_running(test_db, execution.id)
        test_db.refresh(execution)
        assert execution.status == "running"
        assert execution.started_at is not None

    def test_update_progress(self, test_db, execution):
        update_progress(test_db, execution.id, 42.0, "Creando cursos…", step=3)
        test_db.refresh(execution)
        assert execution.current_phase == "Creando cursos…"
        assert execution.progress_pct == 42.0
        assert execution.current_step == 3

    def test_update_progress_without_step(self, test_db, execution):
        update_progress(test_db, execution.id, 99.0, "Reportes generados")
        test_db.refresh(execution)
        assert execution.progress_pct == 99.0
        assert execution.current_phase == "Reportes generados"

    def test_update_progress_not_found(self, test_db):
        update_progress(test_db, 9999, 50, "test")
        test_db.commit()

    def test_mark_completed(self, test_db, execution):
        metrics = {"categories_created": 1, "total_errors": 2}
        mark_completed(test_db, execution.id, metrics, errors_count=2, duration_seconds=3.5)
        test_db.refresh(execution)
        assert execution.status == "completed"
        assert execution.metrics == metrics
        assert execution.errors_count == 2
        assert execution.duration_seconds == 3.5
        assert execution.current_phase == "Procesamiento completado"
        assert execution.progress_pct == 100

    def test_mark_failed(self, test_db, execution):
        mark_failed(test_db, execution.id, 10.0)
        test_db.refresh(execution)
        assert execution.status == "failed"
        assert execution.completed_at is not None
        assert execution.duration_seconds == 10.0

    def test_set_report_dir(self, test_db, execution):
        set_report_dir(test_db, execution.id, "/reports/42/")
        test_db.refresh(execution)
        assert execution.report_dir == "/reports/42/"

    def test_is_reupload_false(self, test_db, execution):
        assert is_reupload(test_db, execution.semester, execution.modalidad, execution.id) is False

    def test_is_reupload_true(self, test_db, execution):
        prev = Execution(
            filename="prev.xlsx",
            semester=execution.semester,
            mode="both",
            status="completed",
            modalidad=execution.modalidad,
            created_at=datetime.now(UTC),
        )
        test_db.add(prev)
        test_db.commit()
        assert is_reupload(test_db, execution.semester, execution.modalidad, execution.id) is True

    def test_is_reupload_ignores_failed(self, test_db, execution):
        prev = Execution(
            filename="failed.xlsx",
            semester=execution.semester,
            mode="both",
            status="failed",
            modalidad=execution.modalidad,
            created_at=datetime.now(UTC),
        )
        test_db.add(prev)
        test_db.commit()
        assert is_reupload(test_db, execution.semester, execution.modalidad, execution.id) is False

    def test_is_reupload_excludes_self(self, test_db, execution):
        execution.status = "completed"
        test_db.commit()
        assert is_reupload(test_db, execution.semester, execution.modalidad, execution.id) is False


class TestLogRepo:
    def test_save_log(self, test_db, execution):
        save_log(test_db, execution.id, "1", "phase1_complete", identifier="test_sn", detail={"k": "v"})
        test_db.commit()
        logs = test_db.query(ExecutionLog).filter(
            ExecutionLog.execution_id == execution.id
        ).all()
        assert len(logs) == 1
        assert logs[0].phase == "1"
        assert logs[0].action == "phase1_complete"
        assert logs[0].identifier == "test_sn"
        assert logs[0].detail == {"k": "v"}

    def test_save_log_defaults(self, test_db, execution):
        save_log(test_db, execution.id, "2", "test_action")
        test_db.commit()
        log = test_db.query(ExecutionLog).first()
        assert log.identifier is None
        assert log.detail == {}

    def test_save_error(self, test_db, execution):
        save_error(test_db, execution.id, "3", identifier="bad_course", message="Fallo")
        test_db.commit()
        errors = test_db.query(ErrorLog).filter(
            ErrorLog.execution_id == execution.id
        ).all()
        assert len(errors) == 1
        assert errors[0].type == "3"
        assert errors[0].identifier == "bad_course"
        assert errors[0].message == "Fallo"
