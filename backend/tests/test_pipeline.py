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
# Phase3 y Phase4 usan el patrón chord + item_task, no clases phase directas


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
