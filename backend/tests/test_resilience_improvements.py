"""
Pruebas unitarias de las mejoras M1-M4:

- M1.1: process_etl_item marca 'failed' tras agotar reintentos por sobrecarga.
- M1.3: marcador chord_active (set/clear) para el sweeper.
- M2.1: resolución de usuarios por username/cédula + detección de identidad.
- M2.2: create_user_if_not_exists recupera usuarios existentes por username.
- M3: spanish_message preserva el errorcode de Moodle.
- M4: recreate atómico (borrar + crear) propagado hasta create_course.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.moodle import MoodleIntegration
from app.pipeline.course_comparison.apply_action import apply_action
from app.services.moodle_errors import MoodleAPIError, MoodleOverloadedError
from app.services.moodle_operations import MoodleService
from app.workers.phases.item_task import process_etl_item
from app.workers.phases.phase1_consult import _names_differ, _normalize_name


@pytest.fixture
def moodle_integration():
    mock_service = AsyncMock(spec=MoodleService)
    return MoodleIntegration(mock_service)


def _make_item(item_id=1, action="delete", execution_id=1, status="processing", **extra):
    item = MagicMock()
    item.id = item_id
    item.status = status
    item.identifier = "IDENTIFIER_001"
    item.detail = {
        "action": action,
        "execution_id": execution_id,
        "modalidad": "DISTANCIA",
        **extra,
    }
    return item


def _make_moodle():
    m = MagicMock()
    m.close = AsyncMock(return_value=None)
    return m


# ---------------------------------------------------------------------------
# M3: spanish_message preserva el errorcode
# ---------------------------------------------------------------------------
class TestSpanishMessage:
    def test_prefixes_known_errorcode(self):
        err = MoodleAPIError("invalid", "invalidparameter")
        assert err.spanish_message == "[invalidparameter] Parámetro inválido enviado a Moodle."

    def test_no_prefix_without_errorcode(self):
        err = MoodleAPIError("raw message", None)
        assert err.spanish_message == "raw message"

    def test_prefixes_unknown_errorcode(self):
        err = MoodleAPIError("other", "weirdcode")
        assert err.spanish_message == "[weirdcode] other"


# ---------------------------------------------------------------------------
# M2.1: normalización y detección de diferencias de identidad
# ---------------------------------------------------------------------------
class TestNameComparison:
    def test_normalize_removes_accents_and_case(self):
        assert _normalize_name("  MARÍA  José  ") == "maria jose"

    def test_same_name_not_different(self):
        assert _names_differ("María José Suárez", "MARIA JOSE SUAREZ") is False

    def test_different_name_is_different(self):
        assert _names_differ("María José Suárez", "Carlos Andrés López") is True

    def test_minor_token_overlap_not_different(self):
        # Comparten >50% de tokens (apellidos coinciden)
        assert _names_differ("Ana María Pérez", "Ana Pérez") is False

    def test_empty_names_not_different(self):
        assert _names_differ("", "") is False


# ---------------------------------------------------------------------------
# M2.2: create_user_if_not_exists recupera por username
# ---------------------------------------------------------------------------
class TestCreateUserIfNotExistsRecovery:
    @pytest.mark.asyncio
    async def test_existing_user_by_username_returns_not_created(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_users.return_value = []  # no encontrado por email
        integ.service.get_user_by_username.return_value = {
            "username": "teacher1",
            "id": 9,
        }
        username, created = await integ.create_user_if_not_exists(
            {
                "email": "teacher1@ut.edu.co",
                "firstname": "Ana",
                "lastname": "Pérez",
            }
        )
        assert username == "teacher1"
        assert created is False
        integ.service.create_users.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_username_lookup_error_returns_none(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_users.return_value = []
        integ.service.get_user_by_username.side_effect = MoodleAPIError("boom")
        username, created = await integ.create_user_if_not_exists(
            {
                "email": "teacher1@ut.edu.co",
            }
        )
        assert username is None
        assert created is False


# ---------------------------------------------------------------------------
# M4: create_course con recreate atómico
# ---------------------------------------------------------------------------
class TestCreateCourseRecreate:
    @pytest.mark.asyncio
    async def test_recreate_deletes_then_creates(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.side_effect = [
            [{"shortname": "EXISTING", "id": "1"}],  # existe → borrar
            [],  # verificación: ya no existe
            [{"shortname": "EXISTING", "id": "2"}],  # creado
        ]
        integ.service.delete_courses.return_value = {"status": "ok"}
        integ.service.create_courses.return_value = [{"shortname": "EXISTING", "id": "2"}]
        result = await integ.create_course(
            "EXISTING",
            "Existing",
            "CAT-01",
            recreate=True,
        )
        assert result is True
        integ.service.delete_courses.assert_awaited_once_with(["EXISTING"])

    @pytest.mark.asyncio
    async def test_recreate_returns_false_if_course_persists(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.return_value = [{"shortname": "EXISTING", "id": "1"}]
        integ.service.delete_courses.return_value = None  # no borra
        result = await integ.create_course(
            "EXISTING",
            "Existing",
            "CAT-01",
            recreate=True,
        )
        assert result is False
        assert "persiste" in integ.last_error

    @pytest.mark.asyncio
    async def test_no_recreate_skips_existing(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.return_value = [{"shortname": "EXISTING", "id": "1"}]
        result = await integ.create_course("EXISTING", "Existing", "CAT-01")
        assert result is True
        integ.service.delete_courses.assert_not_awaited()


# ---------------------------------------------------------------------------
# M4: apply_action propaga "recreate": True a to_create
# ---------------------------------------------------------------------------
class TestApplyActionRecreate:
    def test_recreate_adds_flag_to_create(self):
        to_create, to_delete = [], []
        apply_action(
            "recreate",
            {"old_shortname": "OLD-1", "reason": "contenido renovado"},
            "NEW-1",
            "prof",
            None,
            to_create,
            to_delete,
            [],
            [],
            [],
            [],
            [],
        )
        assert to_delete == [
            {
                "shortname": "OLD-1",
                "old_shortname": "OLD-1",
                "reason": "contenido renovado",
            }
        ]
        assert to_create == [
            {
                "shortname": "NEW-1",
                "professor": "prof",
                "recreate": True,
                "reason": "contenido renovado",
                "old_shortname": "OLD-1",
            }
        ]

    def test_plain_create_has_no_recreate_flag(self):
        to_create, to_delete = [], []
        apply_action(
            "create",
            {},
            "NEW-1",
            "prof",
            None,
            to_create,
            to_delete,
            [],
            [],
            [],
            [],
            [],
        )
        assert to_create == [{"shortname": "NEW-1", "professor": "prof"}]


# ---------------------------------------------------------------------------
# M4: item_task pasa recreate desde el detail del item
# ---------------------------------------------------------------------------
class TestItemTaskRecreate:
    def test_create_course_receives_recreate_flag(self):
        item = MagicMock()
        item.id = 1
        item.status = "pending"
        item.identifier = "IDENTIFIER_001"
        item.detail = {
            "action": "create",
            "execution_id": 1,
            "modalidad": "DISTANCIA",
            "fullname": "New Course",
            "category_idnumber": "CAT_01",
            "template_id": None,
            "recreate": True,
        }
        moodle = MagicMock()
        moodle.close = AsyncMock(return_value=None)
        mock_integ = AsyncMock()
        mock_integ.create_course.return_value = True
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item", return_value=item),
            patch("app.workers.phases.item_task.get_moodle_service", return_value=moodle),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item"),
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ_cls.return_value = mock_integ
            mock_sl.return_value = MagicMock()
            process_etl_item(1)
        mock_integ.create_course.assert_called_once_with(
            shortname="IDENTIFIER_001",
            fullname="New Course",
            category_idnumber="CAT_01",
            template_id=None,
            recreate=True,
        )


# ---------------------------------------------------------------------------
# M1.1: item agota reintentos por sobrecarga → marcado failed (no rompe chord)
# ---------------------------------------------------------------------------
class TestItemTaskOverloadExhaustion:
    def test_overloaded_exhausts_retries_marks_failed(self):
        moodle = _make_moodle()
        mock_integ = AsyncMock()
        mock_integ.delete_course.side_effect = MoodleOverloadedError("504 gateway time-out")
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch(
                "app.workers.phases.item_task.get_item", return_value=_make_item(action="delete")
            ),
            patch("app.workers.phases.item_task.get_moodle_service", return_value=moodle),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.should_cancel", return_value=False),
            patch("app.workers.phases.item_task.update_item") as mock_update,
            patch("app.workers.phases.item_task._handle_error"),
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
            patch.object(process_etl_item, "max_retries", 0),
        ):
            mock_integ_cls.return_value = mock_integ
            mock_sl.return_value = MagicMock()
            process_etl_item(1)  # no debe lanzar: el chord no debe romperse
        mock_update.assert_any_call(
            mock_sl.return_value,
            1,
            "failed",
            "Agotados reintentos por sobrecarga de Moodle",
        )

    def test_overloaded_before_max_retries_raises(self):
        moodle = _make_moodle()
        mock_integ = AsyncMock()
        mock_integ.delete_course.side_effect = MoodleOverloadedError("504 gateway time-out")
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch(
                "app.workers.phases.item_task.get_item", return_value=_make_item(action="delete")
            ),
            patch("app.workers.phases.item_task.get_moodle_service", return_value=moodle),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.should_cancel", return_value=False),
            patch("app.workers.phases.item_task.update_item") as mock_update,
            patch("app.workers.phases.item_task.claim_item", return_value=True),
            patch.object(process_etl_item, "max_retries", 3),
        ):
            mock_integ_cls.return_value = mock_integ
            mock_sl.return_value = MagicMock()
            with pytest.raises(MoodleOverloadedError):
                process_etl_item(1)  # aún hay reintentos: se relanza para retry de Celery
        for call in mock_update.call_args_list:
            assert "Agotados reintentos" not in str(call)


# ---------------------------------------------------------------------------
# M1.3: marcador chord_active para el sweeper
# ---------------------------------------------------------------------------
class TestChordActiveMarker:
    def test_set_and_clear(self, test_db):
        from app.db.models import Execution
        from app.repositories.execution_repo import clear_chord_active, set_chord_active

        ex = Execution(
            filename="test.xlsx",
            semester="2025A",
            status="running",
            modalidad="DISTANCIA",
            created_at=datetime.now(UTC),
        )
        test_db.add(ex)
        test_db.commit()
        test_db.refresh(ex)

        set_chord_active(test_db, ex.id, minutes=120)
        test_db.refresh(ex)
        active_ts = ex.phase_checkpoint.get("chord_active")
        assert isinstance(active_ts, str)
        future = datetime.fromisoformat(active_ts)
        assert future > datetime.now(UTC)

        clear_chord_active(test_db, ex.id)
        test_db.refresh(ex)
        assert ex.phase_checkpoint.get("chord_active") is None

    def test_chord_active_default_uses_settings(self, test_db):
        from app.core.config import settings
        from app.db.models import Execution
        from app.repositories.execution_repo import set_chord_active

        ex = Execution(
            filename="test.xlsx",
            semester="2025A",
            status="running",
            modalidad="DISTANCIA",
            created_at=datetime.now(UTC),
        )
        test_db.add(ex)
        test_db.commit()
        test_db.refresh(ex)

        set_chord_active(test_db, ex.id)
        test_db.refresh(ex)
        ts = datetime.fromisoformat(ex.phase_checkpoint["chord_active"])
        expected = datetime.now(UTC) + timedelta(minutes=settings.CHORD_ACTIVE_MINUTES)
        assert abs((ts - expected).total_seconds()) < 5


# ---------------------------------------------------------------------------
# M1.4: sweeper recover_stuck_phase relanza fases con chord huérfano
# ---------------------------------------------------------------------------
class TestRecoverStuckPhase:
    def _make_execution(self, test_db, status="running", checkpoint=None):
        from app.db.models import Execution

        ex = Execution(
            filename="test.xlsx",
            semester="2025A",
            status=status,
            modalidad="DISTANCIA",
            created_at=datetime.now(UTC),
            phase_checkpoint=checkpoint or {},
        )
        test_db.add(ex)
        test_db.commit()
        test_db.refresh(ex)
        return ex

    def test_relaunches_phase3_when_chord_expired(self, test_db):
        ex = self._make_execution(test_db)
        with (
            patch("app.workers.phases.common._get_pending_items", return_value=[MagicMock()]),
            patch("app.workers.utils.reset_stuck_items", return_value=[]),
            patch("app.workers.phases.phase3_structure.on_delete_items_done") as mock_cb,
        ):
            from app.workers.cleanup_tasks import recover_stuck_phase

            recover_stuck_phase()
        mock_cb.delay.assert_called_once_with([], ex.id)

    def test_relaunches_phase4(self, test_db):
        ex = self._make_execution(test_db)
        with (
            patch("app.workers.phases.common._get_pending_items", side_effect=[[], [MagicMock()]]),
            patch("app.workers.utils.reset_stuck_items", return_value=[]),
            patch("app.workers.cleanup_tasks._relaunch_phase4") as mock_relaunch,
        ):
            from app.workers.cleanup_tasks import recover_stuck_phase

            recover_stuck_phase()
        mock_relaunch.assert_called_once()
        assert mock_relaunch.call_args.args[1] == ex.id

    def test_skips_relaunch_when_chord_active(self, test_db):
        future = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        self._make_execution(test_db, checkpoint={"chord_active": future})
        with (
            patch(
                "app.workers.phases.common._get_pending_items", return_value=[MagicMock()]
            ) as mock_get,
            patch("app.workers.utils.reset_stuck_items", return_value=[]),
            patch("app.workers.phases.phase3_structure.on_delete_items_done") as mock_cb,
        ):
            from app.workers.cleanup_tasks import recover_stuck_phase

            recover_stuck_phase()
        mock_get.assert_called()
        mock_cb.delay.assert_not_called()

    def test_phase4_relaunch_refreshes_chord_active(self, test_db):
        from app.workers.phases.common import on_phase_items_done

        ex = self._make_execution(test_db)
        with (
            patch("app.workers.phases.common._get_pending_items", return_value=[MagicMock()]),
            patch("app.workers.phases.common.reset_stuck_items", return_value=[]),
            patch("app.workers.phases.common.process_etl_item") as mock_task,
            patch("app.workers.phases.common.chord") as mock_chord,
            patch("app.workers.phases.common._mark_chord_active") as mock_mark,
        ):
            mock_task.si.return_value = "sig1"
            mock_chord.return_value = MagicMock()
            on_phase_items_done([], ex.id, "4")
        mock_mark.assert_called_once_with(ex.id)
        mock_chord.assert_called_once()

    def test_relaunches_phase12_when_stale_and_no_items(self, test_db):
        old = datetime.now(UTC) - timedelta(minutes=40)
        ex = self._make_execution(test_db, checkpoint={"_retry_count": 0})
        ex.progress_updated_at = old
        ex.created_at = old
        test_db.commit()
        with (
            patch("app.workers.phases.common._get_pending_items", side_effect=[[], []]),
            patch("app.workers.phases.common._items_exist_for_execution", return_value=False),
            patch("app.workers.tasks.process_etl_file") as mock_file,
            patch("os.path.isfile", return_value=True),
        ):
            from app.workers.cleanup_tasks import recover_stuck_phase

            recover_stuck_phase()
        mock_file.delay.assert_called_once()
        args = mock_file.delay.call_args[0]
        assert args[0] == ex.id

    def test_skips_relaunch_phase12_when_heartbeat_recent(self, test_db):
        fresh = datetime.now(UTC) - timedelta(minutes=5)
        ex = self._make_execution(test_db, checkpoint={"_retry_count": 0})
        ex.progress_updated_at = fresh
        ex.created_at = fresh
        test_db.commit()
        with (
            patch("app.workers.phases.common._get_pending_items", side_effect=[[], []]),
            patch("app.workers.phases.common._items_exist_for_execution", return_value=False),
            patch("app.workers.tasks.process_etl_file") as mock_file,
        ):
            from app.workers.cleanup_tasks import recover_stuck_phase

            recover_stuck_phase()
        mock_file.delay.assert_not_called()

    def test_skips_relaunch_phase12_when_retry_exceeded(self, test_db):
        old = datetime.now(UTC) - timedelta(minutes=40)
        ex = self._make_execution(test_db, checkpoint={"_retry_count": 3})
        ex.progress_updated_at = old
        ex.created_at = old
        test_db.commit()
        with (
            patch("app.workers.phases.common._get_pending_items", side_effect=[[], []]),
            patch("app.workers.phases.common._items_exist_for_execution", return_value=False),
            patch("app.workers.tasks.process_etl_file") as mock_file,
            patch("os.path.isfile", return_value=True),
        ):
            from app.workers.cleanup_tasks import recover_stuck_phase

            recover_stuck_phase()
        mock_file.delay.assert_not_called()


# ---------------------------------------------------------------------------
# enrol_failed — normalización de motivos de fallo de matrícula
# ---------------------------------------------------------------------------
class TestNormalizeEnrolReason:
    def test_user_not_found_spanish(self):
        from app.workers.phases.item_task import _normalize_enrol_reason

        assert _normalize_enrol_reason("Usuario no encontrado en Moodle: u1") == "user_not_found"

    def test_user_inactive_by_code(self):
        from app.workers.phases.item_task import _normalize_enrol_reason

        assert _normalize_enrol_reason("usernotactive: user suspended") == "user_inactive"

    def test_course_not_found(self):
        from app.workers.phases.item_task import _normalize_enrol_reason

        assert _normalize_enrol_reason("Curso no encontrado en Moodle: C1") == "course_not_found"

    def test_fallback_raw(self):
        from app.workers.phases.item_task import _normalize_enrol_reason

        assert _normalize_enrol_reason("unknown weird error") == "unknown weird error"


# ---------------------------------------------------------------------------
# CAS: claim_item atómico
# ---------------------------------------------------------------------------
class TestClaimItem:
    def test_claims_from_pending(self, test_db):
        from app.db.models import OperationBatch, OperationItem
        from app.repositories.operation_repo import claim_item

        batch = OperationBatch(
            batch_id="etl_test_claim",
            entity_type="test",
            action="test",
            total=1,
            modalidad="DISTANCIA",
        )
        test_db.add(batch)
        test_db.flush()
        item = OperationItem(
            batch_id="etl_test_claim",
            identifier="ID1",
            detail={"action": "test"},
            status="pending",
        )
        test_db.add(item)
        test_db.flush()
        item_id = item.id
        assert claim_item(test_db, item_id) is True
        test_db.refresh(item)
        assert item.status == "processing"

    def test_second_claim_fails(self, test_db):
        from app.db.models import OperationBatch, OperationItem
        from app.repositories.operation_repo import claim_item

        batch = OperationBatch(
            batch_id="etl_test_claim2",
            entity_type="test",
            action="test",
            total=1,
            modalidad="DISTANCIA",
        )
        test_db.add(batch)
        test_db.flush()
        item = OperationItem(
            batch_id="etl_test_claim2",
            identifier="ID1",
            detail={"action": "test"},
            status="pending",
        )
        test_db.add(item)
        test_db.flush()
        item_id = item.id
        assert claim_item(test_db, item_id) is True
        assert claim_item(test_db, item_id) is False


# ---------------------------------------------------------------------------
# Chord ordering: set_chord_active antes de lanzar
# ---------------------------------------------------------------------------
class TestChordActiveOrdering:
    def test_launch_items_chord_marks_before_chord(self):
        from app.workers.phases.common import _launch_items_chord

        item = MagicMock()
        item.id = 1
        calls = []
        with (
            patch("app.workers.phases.common.chord") as mock_chord_fn,
            patch("app.workers.phases.common._mark_chord_active") as mock_mark,
        ):
            mock_mark.side_effect = lambda *a, **kw: calls.append("mark")
            mock_chord_fn.side_effect = lambda *a, **kw: calls.append("chord") or MagicMock()
            _launch_items_chord(1, [item])
        assert calls == ["mark", "chord"]

    def test_launch_delete_chord_marks_before_chord(self):
        from app.workers.phases.phase3_structure import _launch_delete_chord

        item = MagicMock()
        item.id = 1
        calls = []
        with (
            patch("app.workers.phases.phase3_structure.chord") as mock_chord_fn,
            patch("app.workers.phases.phase3_structure._mark_delete_chord_active") as mock_mark,
        ):
            mock_mark.side_effect = lambda *a, **kw: calls.append("mark")
            mock_chord_fn.side_effect = lambda *a, **kw: calls.append("chord") or MagicMock()
            _launch_delete_chord(1, [item])
        assert calls == ["mark", "chord"]


# ---------------------------------------------------------------------------
# M2.5: reset de items 'failed' reintentables con tope de intentos
# ---------------------------------------------------------------------------
class TestResetFailedItems:
    def test_resets_failed_below_attempt_cap(self, test_db):
        from app.db.models import Execution, OperationItem
        from app.workers.phases.common import _reset_failed_items

        ex = Execution(
            filename="test.xlsx", semester="2025A", status="running", modalidad="DISTANCIA"
        )
        test_db.add(ex)
        test_db.commit()

        retryable = OperationItem(
            batch_id=f"etl_3_activate_{ex.id}",
            identifier="A",
            status="failed",
            attempt=1,
            detail={"action": "activate"},
        )
        exhausted = OperationItem(
            batch_id=f"etl_3_activate_{ex.id}",
            identifier="B",
            status="failed",
            attempt=3,
            detail={"action": "activate"},
        )
        test_db.add_all([retryable, exhausted])
        test_db.commit()

        _reset_failed_items(test_db, ex.id, "3")

        test_db.refresh(retryable)
        test_db.refresh(exhausted)
        assert retryable.status == "pending"
        assert exhausted.status == "failed"


# ---------------------------------------------------------------------------
# M3.2: sweeper resetea items individuales atascados pese a actividad reciente
# ---------------------------------------------------------------------------
class TestSweeperResetsStaleItems:
    def _stale_item(self, test_db, eid, batch, identifier, minutes_ago):
        from app.db.models import OperationItem

        item = OperationItem(
            batch_id=batch,
            identifier=identifier,
            status="processing",
            detail={"action": "create"},
            updated_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )
        test_db.add(item)
        return item

    def test_resets_stale_item_even_with_recent_activity(self, test_db):
        from app.db.models import Execution
        from app.workers.cleanup_tasks import recover_stuck_phase

        ex = Execution(
            filename="test.xlsx", semester="2025A", status="running", modalidad="DISTANCIA"
        )
        test_db.add(ex)
        test_db.commit()

        stale = self._stale_item(test_db, ex.id, f"etl_3_hide_{ex.id}", "stale-1", minutes_ago=60)
        recent = self._stale_item(
            test_db, ex.id, f"etl_3_create_{ex.id}", "recent-1", minutes_ago=1
        )
        test_db.commit()

        with patch("app.workers.phases.common._get_pending_items", return_value=[]):
            recover_stuck_phase()

        test_db.refresh(stale)
        test_db.refresh(recent)
        assert stale.status == "pending"
        assert recent.status == "processing"


# ---------------------------------------------------------------------------
# M4.1: sync de contadores de lote ETL desde operation_items
# ---------------------------------------------------------------------------
class TestSyncBatchCounts:
    def test_updates_batch_totals_from_items(self, test_db):
        from app.db.models import Execution
        from app.repositories.operation_repo import add_item, create_batch
        from app.workers.phases.common import _sync_batch_counts

        ex = Execution(
            filename="test.xlsx", semester="2025A", status="running", modalidad="DISTANCIA"
        )
        test_db.add(ex)
        test_db.commit()

        batch_id = f"etl_3_activate_{ex.id}"
        batch = create_batch(test_db, batch_id, "courses", "activate", 3, "DISTANCIA")
        add_item(test_db, batch_id, "A", {"action": "activate"}, status="completed")
        add_item(test_db, batch_id, "B", {"action": "activate"}, status="completed")
        add_item(test_db, batch_id, "C", {"action": "activate"}, status="failed")
        test_db.commit()

        _sync_batch_counts(test_db, ex.id)

        test_db.refresh(batch)
        assert batch.completed == 2
        assert batch.failed == 1
