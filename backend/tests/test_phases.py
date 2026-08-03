"""
Pruebas unitarias para cada fase del pipeline ETL.

Cada fase se prueba de forma aislada con un PhaseContext sintético
y un MoodleService/AuthIntegration mockeado.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.db.models import Execution, ExecutionLog
from app.integrations.moodle import MoodleIntegration
from app.workers.phases.base import PhaseContext
from app.workers.phases.phase1_consult import ConsultPhase
from app.workers.phases.phase2_analyze import AnalyzePhase, persist_plan_logs
# Phase3 y Phase4 usan el patrón chord + item_task, no clases phase directas


def _make_ctx(test_db, mock_moodle, mode="both"):
    execution = Execution(
        filename="test.xlsx",
        semester="2025A",
        mode=mode,
        status="pending",
        modalidad="DISTANCIA",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(execution)
    test_db.commit()
    test_db.refresh(execution)

    integration = MoodleIntegration(mock_moodle)

    etl_data = {
        "categories": [
            {"name": "TestCat", "idnumber": "IDE", "parent": 0},
        ],
        "courses": [
            {
                "shortname": "IDE_0001_sI_101_G-01",
                "fullname": "CURSO DE PRUEBA - GRUPO 01",
                "category_idnumber": "IDE_0001_sI",
                "templatecourse": "PORTAFOLIO_0001_sI_101",
            },
        ],
        "users": [
            {
                "username": "doc1",
                "email": "doc1@ut.edu.co",
                "email_personal": "doc1@gmail.com",
                "firstname": "Docente",
                "lastname": "Uno",
                "cedula": "12345",
                "city": "IBAGUÉ",
                "description": "",
            },
        ],
        "enrolments": [
            {"username": "doc1", "course_shortname": "IDE_0001_sI_101_G-01", "role": "editingteacher"},
        ],
    }

    return PhaseContext(
        db=test_db,
        execution_id=execution.id,
        execution=execution,
        mode=mode,
        semester="2025A",
        etl_data=etl_data,
        moodle_service=mock_moodle,
        integration=integration,
    )


class TestConsultPhase:
    @pytest.mark.asyncio
    async def test_happy_path(self, test_db, mock_moodle_service):
        mock_moodle_service.get_categories.return_value = [
            {"id": 1, "idnumber": "IDE", "name": "TestCat"},
        ]
        mock_moodle_service.get_courses.return_value = [
            {"id": 10, "shortname": "IDE_0001_sI_101_G-01", "fullname": "CURSO"},
        ]
        mock_find = AsyncMock()
        with patch.object(MoodleIntegration, "find_users_by_emails", new=mock_find):
            mock_find.return_value = {"doc1@ut.edu.co": {"username": "doc1", "email": "doc1@ut.edu.co"}}

            ctx = _make_ctx(test_db, mock_moodle_service)
            phase = ConsultPhase()
            await phase.run(ctx)

        assert len(ctx.existing_cat_idnumbers) == 1
        assert "IDE" in ctx.existing_cat_idnumbers
        assert len(ctx.existing_courses) == 1
        assert ctx.username_map == {"doc1": "doc1"}

    @pytest.mark.asyncio
    async def test_raises_on_failure(self, test_db, mock_moodle_service):
        mock_moodle_service.get_categories.side_effect = Exception("Moodle caído")
        ctx = _make_ctx(test_db, mock_moodle_service)
        phase = ConsultPhase()
        with pytest.raises(Exception, match="Moodle caído"):
            await phase.run(ctx)
        assert ctx.metrics["total_errors"] >= 1

    @pytest.mark.asyncio
    async def test_resolves_user_by_username_when_email_missing(self, test_db, mock_moodle_service):
        mock_moodle_service.get_categories.return_value = []
        mock_moodle_service.get_courses.return_value = []
        with patch.object(MoodleIntegration, "find_users_by_emails", new=AsyncMock(return_value={})), \
             patch.object(MoodleIntegration, "find_users_by_usernames",
                          new=AsyncMock(return_value={
                              "doc1": {"username": "doc1", "firstname": "Docente", "lastname": "Uno"},
                          })), \
             patch.object(MoodleIntegration, "find_users_by_idnumbers", new=AsyncMock(return_value={})):
            ctx = _make_ctx(test_db, mock_moodle_service)
            phase = ConsultPhase()
            await phase.run(ctx)

        assert ctx.username_map == {"doc1": "doc1"}

    @pytest.mark.asyncio
    async def test_username_match_with_different_name_is_flagged(self, test_db, mock_moodle_service):
        mock_moodle_service.get_categories.return_value = []
        mock_moodle_service.get_courses.return_value = []
        with patch.object(MoodleIntegration, "find_users_by_emails", new=AsyncMock(return_value={})), \
             patch.object(MoodleIntegration, "find_users_by_usernames",
                          new=AsyncMock(return_value={
                              "doc1": {"username": "doc1", "firstname": "Carlos", "lastname": "Andres"},
                          })), \
             patch.object(MoodleIntegration, "find_users_by_idnumbers", new=AsyncMock(return_value={})):
            ctx = _make_ctx(test_db, mock_moodle_service)
            phase = ConsultPhase()
            await phase.run(ctx)

        # Nombre ETL "Docente Uno" != Moodle "Carlos Andres" → no se mapea
        assert ctx.username_map == {}


class TestAnalyzePhase:
    @pytest.mark.asyncio
    async def test_detects_missing_categories_and_users_to_create(self, test_db, mock_moodle_service):
        ctx = _make_ctx(test_db, mock_moodle_service)
        ctx.existing_cat_idnumbers = set()
        ctx.username_map = {}

        mock_moodle_service.get_enrolled_teachers.return_value = []
        ctx.courses_with_teacher = set()
        ctx.existing_courses = []

        phase = AnalyzePhase()
        await phase.run(ctx)

        assert len(ctx.missing_categories) == 1
        assert ctx.missing_categories[0]["idnumber"] == "IDE"
        assert len(ctx.users_to_create) == 1
        assert ctx.users_to_create[0]["username"] == "doc1"

    @pytest.mark.asyncio
    async def test_no_users_to_create_when_resolved(self, test_db, mock_moodle_service):
        ctx = _make_ctx(test_db, mock_moodle_service)
        ctx.existing_cat_idnumbers = {"IDE"}
        ctx.username_map = {"doc1": "doc1"}
        ctx.existing_courses = []
        ctx.courses_with_teacher = set()

        mock_moodle_service.get_enrolled_teachers.return_value = []

        phase = AnalyzePhase()
        await phase.run(ctx)

        assert len(ctx.users_to_create) == 0

    @pytest.mark.asyncio
    async def test_raises_on_failure(self, test_db, mock_moodle_service):
        ctx = _make_ctx(test_db, mock_moodle_service)
        with patch("app.workers.phases.phase2_analyze.CourseComparisonService") as mock_compare:
            mock_compare.compare.side_effect = Exception("Error de análisis")
            phase = AnalyzePhase()
            with pytest.raises(Exception, match="Error de análisis"):
                await phase.run(ctx)
            assert ctx.metrics["total_errors"] >= 1


class TestPersistPlanLogs:
    def test_persists_plan_logs_and_alerts(self, test_db):
        execution = Execution(
            filename="test.xlsx",
            semester="2025A",
            mode="both",
            status="pending",
            modalidad="DISTANCIA",
            created_at=datetime.now(timezone.utc),
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)

        comparison = {
            "logs": [
                {"action": "course_created", "identifier": "C1",
                 "detail": {"reason": "new", "professor": "p1"}},
                {"action": "course_deleted", "identifier": "C2",
                 "detail": {"reason": "disappeared", "age_seconds": 864000}},
            ],
            "alerts": [
                {"shortname": "C3", "reason": "disappeared_recent",
                 "age_seconds": 7200},
                {"shortname": "C4", "reason": "teacher_change_recent",
                 "old_professor": "p1", "new_professor": "p2"},
                {"shortname": "C5", "reason": "reason_desconocido"},
            ],
        }

        count = persist_plan_logs(test_db, execution.id, comparison)

        assert count == 4
        logs = (
            test_db.query(ExecutionLog)
            .filter(ExecutionLog.execution_id == execution.id)
            .order_by(ExecutionLog.id)
            .all()
        )
        assert [l.action for l in logs] == [
            "planned_course_created",
            "planned_course_deleted",
            "alert_disappeared_recent",
            "alert_teacher_change_recent",
        ]
        assert logs[0].phase == "2"
        assert logs[0].identifier == "C1"
        assert logs[0].detail["reason"] == "new"
        assert logs[1].identifier == "C2"
        assert logs[1].detail["age_seconds"] == 864000
        assert logs[2].identifier == "C3"
        assert logs[2].detail["age_seconds"] == 7200
        assert logs[3].identifier == "C4"
        assert logs[3].detail["new_professor"] == "p2"
        assert logs[3].detail.get("professor") == "p2"
        assert logs[3].detail.get("fullname") == ""

    def test_persists_alert_fullname_and_professor_from_map(self, test_db):
        execution = Execution(
            filename="test.xlsx", semester="2025A", mode="both",
            status="pending", modalidad="DISTANCIA",
            created_at=datetime.now(timezone.utc),
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)

        comparison = {
            "alerts": [
                {"shortname": "C1", "reason": "disappeared_recent",
                 "age_seconds": 3600},
                {"shortname": "C2", "reason": "teacher_change_recent",
                 "old_professor": "oldp", "new_professor": "newp"},
            ],
        }
        fullname_map = {"C1": "Curso Uno", "C2": "Curso Dos"}

        persist_plan_logs(test_db, execution.id, comparison, fullname_map)

        logs = (
            test_db.query(ExecutionLog)
            .filter(ExecutionLog.execution_id == execution.id)
            .order_by(ExecutionLog.id)
            .all()
        )
        assert logs[0].detail["fullname"] == "Curso Uno"
        assert logs[0].detail.get("professor") == ""
        assert logs[1].detail["fullname"] == "Curso Dos"
        assert logs[1].detail["professor"] == "newp"


