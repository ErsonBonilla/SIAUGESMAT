"""
Pruebas unitarias para cada fase del pipeline ETL.

Cada fase se prueba de forma aislada con un PhaseContext sintético
y un MoodleService/AuthIntegration mockeado.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.models import Execution
from app.integrations.moodle import MoodleIntegration
from app.workers.phases.base import PhaseContext
from app.workers.phases.phase1_consult import ConsultPhase
from app.workers.phases.phase2_analyze import AnalyzePhase
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


