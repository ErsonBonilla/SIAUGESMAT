from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Execution
from app.workers.phases.base import PhaseContext
from app.workers.phases.orchestrator import (
    _inc_retry_count,
    _is_delete_confirmed,
    _require_review,
    _restore_checkpoint,
    _restore_progress_checkpoint,
    _save_phase_checkpoint,
    _save_phase_2_data_to_checkpoint,
    _serialize_comparison,
    process_etl_phase,
)


@pytest.fixture
def execution(test_db):
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


@pytest.fixture
def ctx(test_db, execution):
    return PhaseContext(
        db=test_db,
        execution_id=execution.id,
        execution=execution,
        mode="both",
        semester="2025A",
        etl_data={"courses": [], "users": []},
        moodle_service=MagicMock(),
        integration=MagicMock(),
    )


class TestSerialization:
    def test_empty(self):
        assert _serialize_comparison({}) == {}

    def test_sets_to_lists(self):
        result = _serialize_comparison({"to_delete": {"a", "b"}, "logs": []})
        assert set(result["to_delete"]) == {"a", "b"}
        assert "logs" not in result

    def test_preserves_lists(self):
        result = _serialize_comparison({"to_delete": ["a"], "to_create": []})
        assert result == {"to_delete": ["a"], "to_create": []}


class TestRestoreCheckpoint:
    def test_phase1(self, ctx):
        data = {
            "cat_idnumbers": ["IDE"],
            "courses": [{"shortname": "C1"}],
            "username_map": {"doc1": "doc1"},
            "courses_with_teacher": {"C1": "doc1"},
        }
        _restore_checkpoint(ctx, data, "1")
        assert ctx.existing_cat_idnumbers == {"IDE"}
        assert ctx.existing_courses == [{"shortname": "C1"}]
        assert ctx.username_map == {"doc1": "doc1"}
        assert ctx.courses_with_teacher == {"C1": "doc1"}

    def test_phase2(self, ctx):
        data = {
            "comparison": {"to_create": ["c1"]},
            "missing_categories": [{"idnumber": "CAT"}],
            "categories_to_relocate": [],
            "users_to_create": [{"username": "u1"}],
            "resolved_enrolments": [],
            "re_upload": True,
        }
        _restore_checkpoint(ctx, data, "2")
        assert ctx.comparison == {"to_create": ["c1"]}
        assert ctx.missing_categories == [{"idnumber": "CAT"}]
        assert ctx.re_upload is True
        assert ctx.users_to_create == [{"username": "u1"}]

    def test_restore_progress(self, ctx):
        data = {"metrics": {"courses_created": 5}, "username_map": {"u1": "u1"}}
        _restore_progress_checkpoint(ctx, data, "1")
        assert ctx.metrics["courses_created"] == 5
        assert ctx.username_map == {"u1": "u1"}


class TestSavePhaseCheckpoint:
    def test_phase1(self, test_db, execution, ctx):
        ctx.existing_cat_idnumbers = {"IDE"}
        ctx.existing_courses = [{"shortname": "C1"}]
        ctx.username_map = {"doc1": "doc1"}
        ctx.courses_with_teacher = {"C1": "doc1"}
        _save_phase_checkpoint(test_db, execution.id, ctx, "1")
        test_db.refresh(execution)
        cp = execution.phase_checkpoint
        assert "1" in cp
        assert set(cp["1"]["cat_idnumbers"]) == {"IDE"}

    def test_phase2(self, test_db, execution, ctx):
        ctx.comparison = {"to_delete": ["c1"]}
        ctx.missing_categories = [{"idnumber": "CAT"}]
        _save_phase_checkpoint(test_db, execution.id, ctx, "2")
        test_db.refresh(execution)
        cp = execution.phase_checkpoint
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
        _save_phase_2_data_to_checkpoint(test_db, execution.id, etl_data, metrics,
                                          phase2_data, "DISTANCIA", "both")
        test_db.refresh(execution)
        cp = execution.phase_checkpoint
        assert "phase3_ctx" in cp
        assert cp["phase3_ctx"]["mode"] == "both"
        assert cp["phase3_ctx"]["modalidad"] == "DISTANCIA"


class TestIsDeleteConfirmed:
    def test_no_execution(self, test_db):
        assert _is_delete_confirmed(test_db, 999) is False

    def test_no_phase_checkpoint(self, test_db, execution):
        assert _is_delete_confirmed(test_db, execution.id) is False

    def test_confirmed_true(self, test_db, execution):
        execution.phase_checkpoint = {"delete_confirmed": True}
        flag_modified(execution, "phase_checkpoint")
        test_db.commit()
        assert _is_delete_confirmed(test_db, execution.id) is True

    def test_confirmed_false(self, test_db, execution):
        execution.phase_checkpoint = {"delete_confirmed": False}
        flag_modified(execution, "phase_checkpoint")
        test_db.commit()
        assert _is_delete_confirmed(test_db, execution.id) is False


class TestRequireReview:
    def test_sets_review_status(self, test_db, execution):
        ctx = MagicMock()
        ctx.comparison.get.return_value = ["c1", "c2"]
        _require_review(test_db, execution.id, ctx)
        test_db.refresh(execution)
        assert execution.status == "review_required"
        assert "Revisión requerida" in execution.current_phase
        assert execution.progress_pct == 30

    def test_no_execution_does_not_raise(self, test_db):
        _require_review(test_db, 999, MagicMock())


class TestIncRetryCount:
    def test_first_call_returns_1(self, test_db, execution):
        assert _inc_retry_count(test_db, execution.id) == 1

    def test_increments(self, test_db, execution):
        assert _inc_retry_count(test_db, execution.id) == 1
        assert _inc_retry_count(test_db, execution.id) == 2

    def test_no_execution_returns_0(self, test_db):
        assert _inc_retry_count(test_db, 999) == 0


class TestProcessEtlPhase:
    def test_execution_not_found(self):
        with patch("app.workers.phases.orchestrator.SessionLocal") as mock_sl, \
             patch("app.workers.phases.orchestrator.get_execution", return_value=None):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            process_etl_phase(1, "3")
            mock_db.close.assert_called_once()

    @pytest.mark.parametrize("status", ["paused", "cancelled"])
    def test_execution_paused_or_cancelled(self, status):
        with patch("app.workers.phases.orchestrator.SessionLocal") as mock_sl, \
             patch("app.workers.phases.orchestrator.get_execution") as mock_get_ex:
            mock_ex = MagicMock()
            mock_ex.status = status
            mock_get_ex.return_value = mock_ex
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            process_etl_phase(1, "3")
            mock_db.close.assert_called_once()

    @patch("app.workers.phases.orchestrator._create_phase3_items", return_value={"delete": 1, "structure": 0})
    @patch("app.workers.phases.orchestrator._get_pending_items")
    @patch("app.workers.phases.orchestrator._launch_delete_chord")
    def test_phase3_delete_items(self, mock_launch, mock_pending, mock_create3):
        mock_pending.side_effect = [[MagicMock()], []]
        with patch("app.workers.phases.orchestrator.SessionLocal") as mock_sl, \
             patch("app.workers.phases.orchestrator.get_execution") as mock_get_ex, \
             patch("app.workers.phases.orchestrator.get_checkpoint") as mock_get_cp:
            mock_ex = MagicMock()
            mock_ex.status = "running"
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
            process_etl_phase(1, "3")
            mock_launch.assert_called_once()

    @patch("app.workers.phases.orchestrator._create_phase3_items", return_value={"delete": 0, "structure": 2})
    @patch("app.workers.phases.orchestrator._get_pending_items")
    @patch("app.workers.phases.orchestrator._launch_items_chord")
    def test_phase3_structure_items(self, mock_launch, mock_pending, mock_create3):
        mock_pending.side_effect = [[], [MagicMock(), MagicMock()]]
        with patch("app.workers.phases.orchestrator.SessionLocal") as mock_sl, \
             patch("app.workers.phases.orchestrator.get_execution") as mock_get_ex, \
             patch("app.workers.phases.orchestrator.get_checkpoint") as mock_get_cp:
            mock_ex = MagicMock()
            mock_ex.status = "running"
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
            process_etl_phase(1, "3")
            mock_launch.assert_called_once()

    @patch("app.workers.phases.orchestrator._create_phase3_items", return_value={"delete": 0, "structure": 0})
    @patch("app.workers.phases.orchestrator.on_phase_items_done")
    def test_phase3_no_items(self, mock_done, mock_create3):
        with patch("app.workers.phases.orchestrator.SessionLocal") as mock_sl, \
             patch("app.workers.phases.orchestrator.get_execution") as mock_get_ex, \
             patch("app.workers.phases.orchestrator.get_checkpoint") as mock_get_cp:
            mock_ex = MagicMock()
            mock_ex.status = "running"
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
            process_etl_phase(1, "3")
            mock_done.delay.assert_called_once_with([], 1, "3")

    @patch("app.workers.phases.orchestrator._create_phase4_items", return_value={"create_user": 1, "enrol": 0})
    @patch("app.workers.phases.orchestrator._get_pending_items")
    @patch("app.workers.phases.orchestrator.on_users_done")
    def test_phase4_users(self, mock_users, mock_pending, mock_create4):
        mock_pending.return_value = [MagicMock()]
        with patch("app.workers.phases.orchestrator.SessionLocal") as mock_sl, \
             patch("app.workers.phases.orchestrator.get_execution") as mock_get_ex, \
             patch("app.workers.phases.orchestrator.get_checkpoint") as mock_get_cp, \
             patch("app.workers.phases.orchestrator.chord") as mock_chord:
            mock_ex = MagicMock()
            mock_ex.status = "running"
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
            process_etl_phase(1, "4")
            mock_chord.assert_called_once()
