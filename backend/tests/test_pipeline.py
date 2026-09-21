"""
Test de integración del pipeline completo.

Verifica que el flujo completo (consulta → análisis → ejecución)
funciona con un Moodle simulado y datos sintéticos.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.db.modelos import Ejecucion
from app.integrations.integracion_moodle import IntegracionMoodle
from app.workers.phases.base import ContextoFase
from app.workers.phases.fase1_consulta import FaseConsulta

# Phase3 y Phase4 usan el patrón chord + item_task, no clases phase directas


@pytest.fixture
def integration_execution(test_db):
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


class TestPipelineIntegration:
    @pytest.mark.asyncio
    async def test_pipeline_detects_failure_on_consult_phase(self, test_db, integration_execution):
        mock = AsyncMock()
        mock.obtener_categorias.side_effect = Exception("API Moodle caída")

        ctx = ContextoFase(
            db=test_db,
            ejecucion_id=integration_execution.id,
            ejecucion=integration_execution,
            modo="both",
            semestre="2025A",
            datos_etl={
                "categories": [],
                "courses": [],
                "users": [],
                "enrolments": [],
            },
            servicio_moodle=mock,
            integracion=IntegracionMoodle(mock),
        )

        phase = FaseConsulta()
        with pytest.raises(Exception, match="API Moodle caída"):
            await phase.ejecutar(ctx)

        assert ctx.metricas["total_errors"] >= 1
