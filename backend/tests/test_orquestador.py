from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.db.modelos import Ejecucion
from app.workers.phases.base import ContextoFase
from app.workers.phases.orquestador import (
    _es_eliminacion_confirmada,
    _guardar_checkpoint_fase,
    _guardar_datos_fase2_en_checkpoint,
    _incrementar_conteo_reintentos,
    _requerir_revision,
    _restaurar_checkpoint,
    _restaurar_checkpoint_progreso,
    _serializar_comparacion,
    procesar_fase_etl,
)


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


@pytest.fixture
def ctx(test_db, execution):
    return ContextoFase(
        db=test_db,
        ejecucion_id=execution.id,
        ejecucion=execution,
        modo="both",
        semestre="2025A",
        datos_etl={"courses": [], "users": []},
        servicio_moodle=MagicMock(),
        integracion=MagicMock(),
    )


class TestSerialization:
    def test_empty(self):
        assert _serializar_comparacion({}) == {}

    def test_sets_to_lists(self):
        result = _serializar_comparacion({"to_delete": {"a", "b"}, "logs": []})
        assert set(result["to_delete"]) == {"a", "b"}
        assert "logs" not in result

    def test_preserves_lists(self):
        result = _serializar_comparacion({"to_delete": ["a"], "to_create": []})
        assert result == {"to_delete": ["a"], "to_create": []}


class TestRestoreCheckpoint:
    def test_phase1(self, ctx):
        data = {
            "cat_idnumbers": ["IDE"],
            "courses": [{"shortname": "C1"}],
            "username_map": {"doc1": "doc1"},
            "courses_with_teacher": {"C1": "doc1"},
        }
        _restaurar_checkpoint(ctx, data, "1")
        assert ctx.idnumeros_categorias_existentes == {"IDE"}
        assert ctx.cursos_existentes == [{"shortname": "C1"}]
        assert ctx.mapa_usuarios == {"doc1": "doc1"}
        assert ctx.cursos_con_docente == {"C1": "doc1"}

    def test_phase2(self, ctx):
        data = {
            "comparison": {"to_create": ["c1"]},
            "missing_categories": [{"idnumber": "CAT"}],
            "categories_to_relocate": [],
            "users_to_create": [{"username": "u1"}],
            "resolved_enrolments": [],
            "re_upload": True,
        }
        _restaurar_checkpoint(ctx, data, "2")
        assert ctx.comparacion == {"to_create": ["c1"]}
        assert ctx.categorias_faltantes == [{"idnumber": "CAT"}]
        assert ctx.nueva_subida is True
        assert ctx.usuarios_a_crear == [{"username": "u1"}]

    def test_restore_progress(self, ctx):
        data = {"metrics": {"courses_created": 5}, "username_map": {"u1": "u1"}}
        _restaurar_checkpoint_progreso(ctx, data, "1")
        assert ctx.metricas["courses_created"] == 5
        assert ctx.mapa_usuarios == {"u1": "u1"}


class TestSavePhaseCheckpoint:
    def test_phase1(self, test_db, execution, ctx):
        ctx.idnumeros_categorias_existentes = {"IDE"}
        ctx.cursos_existentes = [{"shortname": "C1"}]
        ctx.mapa_usuarios = {"doc1": "doc1"}
        ctx.cursos_con_docente = {"C1": "doc1"}
        _guardar_checkpoint_fase(test_db, execution.id, ctx, "1")
        test_db.refresh(execution)
        cp = execution.checkpoint_fase
        assert "1" in cp
        assert set(cp["1"]["cat_idnumbers"]) == {"IDE"}

    def test_phase2(self, test_db, execution, ctx):
        ctx.comparacion = {"to_delete": ["c1"]}
        ctx.categorias_faltantes = [{"idnumber": "CAT"}]
        _guardar_checkpoint_fase(test_db, execution.id, ctx, "2")
        test_db.refresh(execution)
        cp = execution.checkpoint_fase
        assert "2" in cp
        assert cp["2"]["comparison"]["to_delete"] == ["c1"]


class TestSavePhase2Data:
    def test_saves_context(self, test_db, execution):
        etl_data = {"courses": [{"shortname": "C1"}], "users": []}
        metrics = {"courses_created": 0}
        phase2_data = {
            "2": {
                "comparison": {"to_delete": []},
                "missing_categories": [],
                "categories_to_relocate": [],
                "users_to_create": [],
                "resolved_enrolments": [],
            },
            "1": {"username_map": {}},
        }
        _guardar_datos_fase2_en_checkpoint(
            test_db, execution.id, etl_data, metrics, phase2_data, "DISTANCIA", "both"
        )
        test_db.refresh(execution)
        cp = execution.checkpoint_fase
        assert "phase3_ctx" in cp
        assert cp["phase3_ctx"]["mode"] == "both"
        assert cp["phase3_ctx"]["modalidad"] == "DISTANCIA"


class TestIsDeleteConfirmed:
    def test_no_execution(self, test_db):
        assert _es_eliminacion_confirmada(test_db, 999) is False

    def test_no_phase_checkpoint(self, test_db, execution):
        assert _es_eliminacion_confirmada(test_db, execution.id) is False

    def test_confirmed_true(self, test_db, execution):
        execution.checkpoint_fase = {"delete_confirmed": True}
        flag_modified(execution, "checkpoint_fase")
        test_db.commit()
        assert _es_eliminacion_confirmada(test_db, execution.id) is True

    def test_confirmed_false(self, test_db, execution):
        execution.checkpoint_fase = {"delete_confirmed": False}
        flag_modified(execution, "checkpoint_fase")
        test_db.commit()
        assert _es_eliminacion_confirmada(test_db, execution.id) is False


class TestRequireReview:
    def test_sets_review_status(self, test_db, execution):
        ctx = MagicMock()
        ctx.comparacion.get.return_value = ["c1", "c2"]
        _requerir_revision(test_db, execution.id, ctx)
        test_db.refresh(execution)
        assert execution.estado == "review_required"
        assert "Revisión requerida" in execution.fase_actual
        assert execution.porcentaje_progreso == 30

    def test_no_execution_does_not_raise(self, test_db):
        _requerir_revision(test_db, 999, MagicMock())


class TestIncRetryCount:
    def test_first_call_returns_1(self, test_db, execution):
        assert _incrementar_conteo_reintentos(test_db, execution.id) == 1

    def test_increments(self, test_db, execution):
        assert _incrementar_conteo_reintentos(test_db, execution.id) == 1
        assert _incrementar_conteo_reintentos(test_db, execution.id) == 2

    def test_no_execution_returns_0(self, test_db):
        assert _incrementar_conteo_reintentos(test_db, 999) == 0


class TestProcessEtlPhase:
    def test_execution_not_found(self):
        with (
            patch("app.workers.phases.orquestador.SessionLocal") as mock_sl,
            patch("app.workers.phases.orquestador.obtener_ejecucion", return_value=None),
        ):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            procesar_fase_etl(1, "3")
            mock_db.close.assert_called_once()

    @pytest.mark.parametrize("status", ["paused", "cancelled"])
    def test_execution_paused_or_cancelled(self, status):
        with (
            patch("app.workers.phases.orquestador.SessionLocal") as mock_sl,
            patch("app.workers.phases.orquestador.obtener_ejecucion") as mock_get_ex,
        ):
            mock_ex = MagicMock()
            mock_ex.estado = status
            mock_get_ex.return_value = mock_ex
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            procesar_fase_etl(1, "3")
            mock_db.close.assert_called_once()

    @patch(
        "app.workers.phases.orquestador._crear_items_fase3",
        return_value={"delete": 1, "structure": 0},
    )
    @patch("app.workers.phases.orquestador._obtener_items_pendientes")
    @patch("app.workers.phases.orquestador._lanzar_chord_eliminacion")
    def test_phase3_delete_items(self, mock_launch, mock_pending, mock_create3):
        mock_pending.side_effect = [[MagicMock()], []]
        with (
            patch("app.workers.phases.orquestador.SessionLocal") as mock_sl,
            patch("app.workers.phases.orquestador.obtener_ejecucion") as mock_get_ex,
            patch("app.workers.phases.orquestador.obtener_checkpoint") as mock_get_cp,
        ):
            mock_ex = MagicMock()
            mock_ex.estado = "running"
            mock_get_ex.return_value = mock_ex
            mock_get_cp.return_value = {
                "phase3_ctx": {
                    "comparison": {"to_create": ["c1"]},
                    "missing_categories": [],
                    "categories_to_relocate": [],
                    "modalidad": "DISTANCIA",
                    "mode": "both",
                }
            }
            mock_sl.return_value = MagicMock()
            procesar_fase_etl(1, "3")
            mock_launch.assert_called_once()

    @patch(
        "app.workers.phases.orquestador._crear_items_fase3",
        return_value={"delete": 0, "structure": 2},
    )
    @patch("app.workers.phases.orquestador._obtener_items_pendientes")
    @patch("app.workers.phases.orquestador._lanzar_chord_items")
    def test_phase3_structure_items(self, mock_launch, mock_pending, mock_create3):
        mock_pending.side_effect = [[], [MagicMock(), MagicMock()]]
        with (
            patch("app.workers.phases.orquestador.SessionLocal") as mock_sl,
            patch("app.workers.phases.orquestador.obtener_ejecucion") as mock_get_ex,
            patch("app.workers.phases.orquestador.obtener_checkpoint") as mock_get_cp,
        ):
            mock_ex = MagicMock()
            mock_ex.estado = "running"
            mock_get_ex.return_value = mock_ex
            mock_get_cp.return_value = {
                "phase3_ctx": {
                    "comparison": {"to_create": ["c1"]},
                    "missing_categories": [],
                    "categories_to_relocate": [],
                    "modalidad": "DISTANCIA",
                    "mode": "both",
                }
            }
            mock_sl.return_value = MagicMock()
            procesar_fase_etl(1, "3")
            mock_launch.assert_called_once()

    @patch(
        "app.workers.phases.orquestador._crear_items_fase3",
        return_value={"delete": 0, "structure": 0},
    )
    @patch("app.workers.phases.orquestador.al_terminar_items_fase")
    def test_phase3_no_items(self, mock_done, mock_create3):
        with (
            patch("app.workers.phases.orquestador.SessionLocal") as mock_sl,
            patch("app.workers.phases.orquestador.obtener_ejecucion") as mock_get_ex,
            patch("app.workers.phases.orquestador.obtener_checkpoint") as mock_get_cp,
        ):
            mock_ex = MagicMock()
            mock_ex.estado = "running"
            mock_get_ex.return_value = mock_ex
            mock_get_cp.return_value = {
                "phase3_ctx": {
                    "comparison": {"to_create": ["c1"]},
                    "missing_categories": [],
                    "categories_to_relocate": [],
                    "modalidad": "DISTANCIA",
                    "mode": "both",
                }
            }
            mock_sl.return_value = MagicMock()
            procesar_fase_etl(1, "3")
            mock_done.delay.assert_called_once_with([], 1, "3")

    @patch(
        "app.workers.phases.orquestador._crear_items_fase4_sincrono",
        return_value={"create_user": 1, "enrol": 0},
    )
    @patch("app.workers.phases.orquestador._obtener_items_pendientes")
    @patch("app.workers.phases.orquestador.al_terminar_usuarios")
    def test_phase4_users(self, mock_users, mock_pending, mock_create4):
        mock_pending.return_value = [MagicMock()]
        with (
            patch("app.workers.phases.orquestador.SessionLocal") as mock_sl,
            patch("app.workers.phases.orquestador.obtener_ejecucion") as mock_get_ex,
            patch("app.workers.phases.orquestador.obtener_checkpoint") as mock_get_cp,
            patch("app.workers.phases.orquestador.chord") as mock_chord,
        ):
            mock_ex = MagicMock()
            mock_ex.estado = "running"
            mock_get_ex.return_value = mock_ex
            mock_get_cp.return_value = {
                "phase3_ctx": {
                    "comparison": {},
                    "missing_categories": [],
                    "categories_to_relocate": [],
                    "modalidad": "DISTANCIA",
                    "mode": "both",
                }
            }
            mock_sl.return_value = MagicMock()
            procesar_fase_etl(1, "4")
            mock_chord.assert_called_once()
