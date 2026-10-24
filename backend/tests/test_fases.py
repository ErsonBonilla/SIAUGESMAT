"""
Pruebas unitarias para cada fase del pipeline ETL.

Cada fase se prueba de forma aislada con un PhaseContext sintÃ©tico
y un MoodleService/AuthIntegration mockeado.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.db.modelos import Ejecucion, RegistroEjecucion
from app.integrations.integracion_moodle import IntegracionMoodle
from app.workers.phases.base import ContextoFase
from app.workers.phases.fase1_consulta import FaseConsulta
from app.workers.phases.fase2_analisis import FaseAnalisis, persistir_logs_plan

# Phase3 y Phase4 usan el patrÃ³n chord + item_task, no clases phase directas


def _make_ctx(test_db, mock_moodle, modo="both"):
    execution = Ejecucion(
        nombre_archivo="test.xlsx",
        semestre="2025A",
        modo=modo,
        estado="pending",
        modalidad="DISTANCIA",
        creado_en=datetime.now(UTC),
    )
    test_db.add(execution)
    test_db.commit()
    test_db.refresh(execution)

    integration = IntegracionMoodle(mock_moodle)

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
                "city": "IBAGUÃ‰",
                "description": "",
            },
        ],
        "enrolments": [
            {
                "username": "doc1",
                "course_shortname": "IDE_0001_sI_101_G-01",
                "role": "editingteacher",
            },
        ],
    }

    return ContextoFase(
        db=test_db,
        ejecucion_id=execution.id,
        ejecucion=execution,
        modo=modo,
        semestre="2025A",
        datos_etl=etl_data,
        servicio_moodle=mock_moodle,
        integracion=integration,
    )


class TestConsultPhase:
    @pytest.mark.asyncio
    async def test_happy_path(self, test_db, mock_moodle_service):
        mock_moodle_service.obtener_categorias.return_value = [
            {"id": 1, "idnumber": "Distancia", "name": "IDEAD", "parent": 0},
            {"id": 2, "idnumber": "IDE", "name": "TestCat", "parent": 1},
            {"id": 99, "idnumber": "OTRA", "name": "OtraModalidad", "parent": 0},
        ]
        mock_moodle_service.obtener_cursos.return_value = [
            {"id": 10, "shortname": "IDE_0001_sI_101_G-01", "fullname": "CURSO", "categoryid": 2},
            {
                "id": 20,
                "shortname": "OTR_0001_sI_101_G-01",
                "fullname": "EXTERNO",
                "categoryid": 99,
            },
        ]
        mock_find = AsyncMock()
        with patch.object(IntegracionMoodle, "encontrar_usuarios_por_correos", new=mock_find):
            mock_find.return_value = {
                "doc1@ut.edu.co": {"username": "doc1_moodle", "email": "doc1@ut.edu.co"}
            }

            ctx = _make_ctx(test_db, mock_moodle_service)
            phase = FaseConsulta()
            await phase.ejecutar(ctx)

        assert ctx.idnumeros_categorias_existentes == {"Distancia", "IDE"}
        assert "OTRA" not in ctx.idnumeros_categorias_existentes
        assert len(ctx.cursos_existentes) == 1
        assert ctx.cursos_existentes[0]["shortname"] == "IDE_0001_sI_101_G-01"
        assert ctx.mapa_usuarios == {"doc1": "doc1_moodle"}

    @pytest.mark.asyncio
    async def test_raises_on_failure(self, test_db, mock_moodle_service):
        mock_moodle_service.obtener_categorias.side_effect = Exception("Moodle caído")
        ctx = _make_ctx(test_db, mock_moodle_service)
        phase = FaseConsulta()
        with pytest.raises(Exception, match="Moodle caído"):
            await phase.ejecutar(ctx)
        assert ctx.metricas["total_errors"] >= 1

    @pytest.mark.asyncio
    async def test_does_not_resolve_user_when_institutional_email_not_found(
        self, test_db, mock_moodle_service
    ):
        mock_moodle_service.obtener_categorias.return_value = []
        mock_moodle_service.obtener_cursos.return_value = []
        with patch.object(
            IntegracionMoodle, "encontrar_usuarios_por_correos", new=AsyncMock(return_value={})
        ):
            ctx = _make_ctx(test_db, mock_moodle_service)
            phase = FaseConsulta()
            await phase.ejecutar(ctx)

        assert ctx.mapa_usuarios == {}


class TestAnalyzePhase:
    @pytest.mark.asyncio
    async def test_omits_course_and_logs_incidence_when_teacher_missing(
        self, test_db, mock_moodle_service
    ):
        ctx = _make_ctx(test_db, mock_moodle_service)
        ctx.idnumeros_categorias_existentes = set()
        ctx.mapa_usuarios = {}

        mock_moodle_service.obtener_docentes_matriculados.return_value = []
        ctx.cursos_con_docente = set()
        ctx.cursos_existentes = []

        phase = FaseAnalisis()
        await phase.ejecutar(ctx)

        assert len(ctx.categorias_faltantes) == 1
        assert ctx.categorias_faltantes[0]["idnumber"] == "IDE"
        assert ctx.usuarios_a_crear == []
        assert ctx.comparacion["to_create"] == []
        assert ctx.matriculas_resueltas == []

        logs = (
            test_db.query(RegistroEjecucion)
            .filter(
                RegistroEjecucion.ejecucion_id == ctx.ejecucion_id,
                RegistroEjecucion.accion == "course_creation_failed_user_missing",
            )
            .all()
        )
        assert len(logs) == 1
        assert logs[0].identificador == "doc1@ut.edu.co"
        assert logs[0].detalle["shortname"] == "IDE_0001_sI_101_G-01"
        assert logs[0].detalle["firstname"] == "Docente"
        assert logs[0].detalle["lastname"] == "Uno"
        assert logs[0].detalle["cat"] == "IDE"
        assert logs[0].detalle["programa"] == "0001"
        assert logs[0].detalle["semestre"] == "I"
        assert logs[0].detalle["grupo"] == "01"

    @pytest.mark.asyncio
    async def test_creates_course_when_teacher_resolved(self, test_db, mock_moodle_service):
        ctx = _make_ctx(test_db, mock_moodle_service)
        ctx.idnumeros_categorias_existentes = {"IDE"}
        ctx.mapa_usuarios = {"doc1": "doc1_moodle"}
        ctx.cursos_existentes = []
        ctx.cursos_con_docente = set()

        mock_moodle_service.obtener_docentes_matriculados.return_value = []

        phase = FaseAnalisis()
        await phase.ejecutar(ctx)

        assert len(ctx.usuarios_a_crear) == 0
        assert len(ctx.comparacion["to_create"]) == 1
        assert ctx.matriculas_resueltas[0]["username"] == "doc1_moodle"

    @pytest.mark.asyncio
    async def test_raises_on_failure(self, test_db, mock_moodle_service):
        ctx = _make_ctx(test_db, mock_moodle_service)
        with patch("app.workers.phases.fase2_analisis.ServicioComparacionCursos") as mock_compare:
            mock_compare.comparar.side_effect = Exception("Error de anÃ¡lisis")
            phase = FaseAnalisis()
            with pytest.raises(Exception, match="Error de anÃ¡lisis"):
                await phase.ejecutar(ctx)
            assert ctx.metricas["total_errors"] >= 1


class TestPersistPlanLogs:
    def test_persists_plan_logs_and_alerts(self, test_db):
        execution = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025A",
            modo="both",
            estado="pending",
            modalidad="DISTANCIA",
            creado_en=datetime.now(UTC),
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)

        comparison = {
            "logs": [
                {
                    "action": "course_created",
                    "identifier": "C1",
                    "detail": {"reason": "new", "professor": "p1"},
                },
                {
                    "action": "course_deleted",
                    "identifier": "C2",
                    "detail": {"reason": "disappeared", "age_seconds": 864000},
                },
            ],
            "alerts": [
                {"shortname": "C3", "reason": "disappeared_recent", "age_seconds": 7200},
                {
                    "shortname": "C4",
                    "reason": "teacher_change_recent",
                    "old_professor": "p1",
                    "new_professor": "p2",
                },
                {"shortname": "C5", "reason": "reason_desconocido"},
            ],
        }

        count = persistir_logs_plan(test_db, execution.id, comparison)

        assert count == 4
        logs = (
            test_db.query(RegistroEjecucion)
            .filter(RegistroEjecucion.ejecucion_id == execution.id)
            .order_by(RegistroEjecucion.id)
            .all()
        )
        assert [log.accion for log in logs] == [
            "planned_course_created",
            "planned_course_deleted",
            "alert_disappeared_recent",
            "alert_teacher_change_recent",
        ]
        assert logs[0].fase == "2"
        assert logs[0].identificador == "C1"
        assert logs[0].detalle["reason"] == "new"
        assert logs[1].identificador == "C2"
        assert logs[1].detalle["age_seconds"] == 864000
        assert logs[2].identificador == "C3"
        assert logs[2].detalle["age_seconds"] == 7200
        assert logs[3].identificador == "C4"
        assert logs[3].detalle["new_professor"] == "p2"
        assert logs[3].detalle.get("professor") == "p2"
        assert logs[3].detalle.get("fullname") == ""

    def test_persists_alert_fullname_and_professor_from_map(self, test_db):
        execution = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025A",
            modo="both",
            estado="pending",
            modalidad="DISTANCIA",
            creado_en=datetime.now(UTC),
        )
        test_db.add(execution)
        test_db.commit()
        test_db.refresh(execution)

        comparison = {
            "alerts": [
                {"shortname": "C1", "reason": "disappeared_recent", "age_seconds": 3600},
                {
                    "shortname": "C2",
                    "reason": "teacher_change_recent",
                    "old_professor": "oldp",
                    "new_professor": "newp",
                },
            ],
        }
        fullname_map = {"C1": "Curso Uno", "C2": "Curso Dos"}

        persistir_logs_plan(test_db, execution.id, comparison, fullname_map)

        logs = (
            test_db.query(RegistroEjecucion)
            .filter(RegistroEjecucion.ejecucion_id == execution.id)
            .order_by(RegistroEjecucion.id)
            .all()
        )
        assert logs[0].detalle["fullname"] == "Curso Uno"
        assert logs[0].detalle.get("professor") == ""
        assert logs[1].detalle["fullname"] == "Curso Dos"
        assert logs[1].detalle["professor"] == "newp"
