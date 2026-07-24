"""
Test de integración del pipeline completo.

Verifica que el flujo completo (consulta → análisis → ejecución)
funciona con un Moodle simulado y datos sintéticos.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.db.models import Execution
from app.integrations.moodle import MoodleIntegration
from app.workers.phases.base import PhaseContext
from app.workers.phases.phase1_consult import ConsultPhase
from app.workers.phases.phase2_analyze import AnalyzePhase
from app.workers.phases.phase3_execute import ExecutePhase


@pytest.fixture
def integration_execution(test_db):
    ex = Execution(
        filename="test.xlsx",
        semester="2025A",
        mode="both",
        status="pending",
        modalidad="DISTANCIA",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(ex)
    test_db.commit()
    test_db.refresh(ex)
    return ex


class TestPipelineIntegration:

    @pytest.mark.asyncio
    async def test_full_pipeline_happy_path(self, test_db, integration_execution):
        mock = AsyncMock()
        mock.get_categories.return_value = [
            {"id": 1, "idnumber": "IDE", "name": "IDEAD"},
        ]
        mock.get_courses.side_effect = [
            [{"id": 10, "shortname": "IDE_0001_sI_101_G-01"}],
            [{"id": 10, "shortname": "IDE_0001_sI_101_G-01"}],
            [{"id": 99, "shortname": "PORTAFOLIO_0001_sI_101"}],
            [{"id": 10, "shortname": "IDE_0001_sI_101_G-01"}],
            [{"id": 10, "shortname": "IDE_0001_sI_101_G-01"}],
        ]
        mock.get_user_by_username.return_value = {"username": "doc1", "suspended": "0"}
        mock.get_enrolled_teachers.return_value = [{"username": "doc1"}]
        mock.create_categories.return_value = []
        mock.create_courses.return_value = []
        mock.enrol_users.return_value = {"success": True, "errors": []}

        integration = MoodleIntegration(mock)

        async def fake_find(self, email):
            return {"username": "doc1", "email": email}

        with patch.object(MoodleIntegration, "find_user_by_email", new=fake_find):
            async def fake_create(self, user):
                return "doc1", True
            with patch.object(MoodleIntegration, "create_user_if_not_exists", new=fake_create):
                async def fake_enrol(self, username, shortname, courses=None):
                    return {"success": True, "username": username, "reason": "enrolled"}
                with patch.object(MoodleIntegration, "enrol_teacher", new=fake_enrol):
                    async def fake_create_course(self, *a, **kw):
                        return True
                    with patch.object(MoodleIntegration, "create_course", new=fake_create_course):
                        ctx = PhaseContext(
                            db=test_db,
                            execution_id=integration_execution.id,
                            execution=integration_execution,
                            mode="both",
                            semester="2025A",
                            etl_data={
                                "categories": [
                                    {"name": "IDEAD", "idnumber": "IDE", "parent": 0},
                                ],
                                "courses": [
                                    {
                                        "shortname": "IDE_0001_sI_101_G-01",
                                        "fullname": "CURSO PRUEBA - GRUPO 01",
                                        "category_idnumber": "IDE_0001_sI",
                                        "templatecourse": "PORTAFOLIO_0001_sI_101",
                                    },
                                ],
                                "users": [
                                    {
                                        "username": "doc1",
                                        "email": "doc1@ut.edu.co",
                                        "email_personal": "",
                                        "firstname": "Docente",
                                        "lastname": "Uno",
                                        "cedula": "123",
                                        "city": "IBAGUÉ",
                                        "description": "",
                                    },
                                ],
                                "enrolments": [
                                    {"username": "doc1",
                                     "course_shortname": "IDE_0001_sI_101_G-01",
                                     "role": "editingteacher"},
                                ],
                            },
                            moodle_service=mock,
                            integration=integration,
                        )

                        phases = [ConsultPhase(), AnalyzePhase(), ExecutePhase()]
                        for phase in phases:
                            await phase.run(ctx)

        assert ctx.metrics["categories_created"] == 0
        assert ctx.metrics["courses_created"] == 1
        assert ctx.metrics["enrolments"] == 1
        assert ctx.metrics["total_errors"] == 0

    @pytest.mark.asyncio
    async def test_pipeline_detects_failure_on_consult_phase(self, test_db, integration_execution):
        mock = AsyncMock()
        mock.get_categories.side_effect = Exception("API Moodle caída")

        ctx = PhaseContext(
            db=test_db,
            execution_id=integration_execution.id,
            execution=integration_execution,
            mode="both",
            semester="2025A",
            etl_data={
                "categories": [],
                "courses": [],
                "users": [],
                "enrolments": [],
            },
            moodle_service=mock,
            integration=MoodleIntegration(mock),
        )

        phase = ConsultPhase()
        with pytest.raises(Exception, match="API Moodle caída"):
            await phase.run(ctx)

        assert ctx.metrics["total_errors"] >= 1
