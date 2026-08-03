from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.error_messages import translate_error
from app.services.moodle_errors import MoodleAPIError, MoodleOverloadedError
from app.workers.operations_tasks import (
    _ensure_root_category,
    _format_moodle_error,
    process_operation_batch,
)


def _make_moodle():
    m = MagicMock()
    m.close = AsyncMock(return_value=None)
    return m


def _make_batch(batch_id="BATCH_001", entity_type="courses", action="delete", modalidad="DISTANCIA"):
    batch = MagicMock()
    batch.batch_id = batch_id
    batch.entity_type = entity_type
    batch.action = action
    batch.modalidad = modalidad
    return batch


def _make_item(identifier="CURSE_001", **extra):
    item = MagicMock()
    item.id = 1
    item.identifier = identifier
    item.detail = extra
    return item


class TestFormatMoodleError:
    def test_duplicate_user(self):
        e = MagicMock(error_code="duplicateuser", spanish_message="")
        msg = _format_moodle_error(e, "users", _make_item())
        assert "ya existe" in msg

    def test_invalid_email(self):
        e = MagicMock(error_code="invalidemail", spanish_message="")
        item = _make_item(email="bad-email")
        msg = _format_moodle_error(e, "users", item)
        assert "Email inv" in msg

    def test_duplicate_category(self):
        e = MagicMock(error_code="duplicatecategory", spanish_message="")
        msg = _format_moodle_error(e, "categories", _make_item())
        assert "ya existe" in msg

    def test_cannot_find_parent(self):
        e = MagicMock(error_code="cannotfindparentcategory", spanish_message="")
        msg = _format_moodle_error(e, "categories", _make_item())
        assert "no encontrada" in msg

    def test_fallback_to_spanish_message(self):
        e = MagicMock(error_code="unknown_code", spanish_message="Error genérico")
        msg = _format_moodle_error(e, "courses", _make_item())
        assert msg == "Error genérico"


class TestProcessOperationBatch:
    def test_batch_not_found(self):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch", return_value=None):
            db = MagicMock()
            mock_sl.return_value = db
            process_operation_batch("BATCH_001")
            db.close.assert_called_once()

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_delete_courses(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item"), \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="courses", action="delete")
            mock_get_batch.return_value = batch
            item = _make_item()
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.delete_courses = AsyncMock(return_value=[{"id": 1}])
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            process_operation_batch("BATCH_001")
            moodle.delete_courses.assert_called_once_with(["CURSE_001"])
            mock_complete.assert_called_once()
            assert mock_complete.call_args[0][1] == "BATCH_001"

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_delete_course_not_found_idempotent(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item") as mock_update, \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="courses", action="delete")
            mock_get_batch.return_value = batch
            item = _make_item()
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.delete_courses = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            process_operation_batch("BATCH_001")
            mock_update.assert_any_call(
                db, 1, "completed", "Curso no encontrado en Moodle. Se omite (ya no existía)."
            )

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_delete_user_transient_error_but_deleted(self, mock_pending, mock_complete):
        """Error transitorio al borrar pero la entidad ya no existe → completed."""
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item") as mock_update, \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="users", action="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.delete_users = AsyncMock(
                side_effect=MoodleOverloadedError("gateway time-out")
            )
            moodle.get_user_by_username = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            process_operation_batch("BATCH_001")
            mock_update.assert_any_call(db, 1, "completed", None)

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_delete_user_transient_error_still_exists(self, mock_pending, mock_complete):
        """Error transitorio y la entidad sigue existiendo → failed."""
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item") as mock_update, \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="users", action="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.delete_users = AsyncMock(
                side_effect=MoodleOverloadedError("gateway time-out")
            )
            moodle.get_user_by_username = AsyncMock(return_value={"id": 1})
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            process_operation_batch("BATCH_001")
            exc = MoodleOverloadedError("gateway time-out")
            mock_update.assert_any_call(db, 1, "failed", translate_error(exc))

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_delete_user_not_found_idempotent(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item") as mock_update, \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="users", action="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.delete_users = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            process_operation_batch("BATCH_001")
            mock_update.assert_any_call(
                db, 1, "completed", "Usuario no encontrado en Moodle. Se omite (ya no existía)."
            )

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_delete_categories(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item"), \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="categories", action="delete")
            mock_get_batch.return_value = batch
            item = _make_item()
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.get_categories = AsyncMock(return_value=[{"id": 5}])
            moodle.delete_category = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            process_operation_batch("BATCH_001")
            moodle.delete_category.assert_called_once_with(5)

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_delete_users(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item"), \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="users", action="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.delete_users = AsyncMock(return_value=[{"id": 1}])
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            process_operation_batch("BATCH_001")
            moodle.delete_users.assert_called_once_with(["user1"])

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_create_users(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item"), \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="users", action="create")
            mock_get_batch.return_value = batch
            item = _make_item("newuser", firstname="New", lastname="User", email="new@test.com")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.create_users = AsyncMock(return_value=[])
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            process_operation_batch("BATCH_001")
            moodle.create_users.assert_called_once()

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_create_categories(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item"), \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="categories", action="create")
            mock_get_batch.return_value = batch
            item = _make_item("NEWCAT", idnumber="NEWCAT_01")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.create_categories = AsyncMock(return_value=[])
            moodle.get_categories = AsyncMock(return_value=[{"id": 1}])
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            process_operation_batch("BATCH_001")
            moodle.create_categories.assert_called_once()

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_visibility_show(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item"), \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="courses", action="visibility")
            mock_get_batch.return_value = batch
            item = _make_item("CURSE_001", visibility="show")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.get_courses_by_field = AsyncMock(return_value=[{"id": 10}])
            moodle.update_courses = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            process_operation_batch("BATCH_001")
            moodle.update_courses.assert_called_once_with([{"id": 10, "visible": 1}])

    @patch("app.workers.operations_tasks.complete_batch")
    @patch("app.workers.operations_tasks.get_pending_items")
    def test_moodle_api_error_per_item(self, mock_pending, mock_complete):
        with patch("app.workers.operations_tasks.SessionLocal") as mock_sl, \
             patch("app.workers.operations_tasks.get_batch") as mock_get_batch, \
             patch("app.workers.operations_tasks.get_moodle_service", return_value=_make_moodle()) as mock_get_ms, \
             patch("app.workers.operations_tasks.update_item") as mock_update, \
             patch("app.workers.operations_tasks.update_batch_counts"):
            batch = _make_batch(entity_type="courses", action="delete")
            mock_get_batch.return_value = batch
            item = _make_item()
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.delete_courses = AsyncMock(side_effect=MoodleAPIError("API error", "unknownerror"))
            moodle.get_courses = AsyncMock(return_value=[{"id": 1}])
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            process_operation_batch("BATCH_001")
            mock_update.assert_any_call(db, 1, "failed", "[unknownerror] API error")


class TestEnsureRootCategory:
    @pytest.mark.asyncio
    async def test_already_exists(self):
        moodle = AsyncMock()
        moodle.get_categories.return_value = [{"id": 1}]
        await _ensure_root_category(moodle)
        moodle.create_categories.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_when_missing(self):
        moodle = AsyncMock()
        moodle.get_categories.return_value = []
        await _ensure_root_category(moodle)
        moodle.create_categories.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_on_error(self):
        moodle = AsyncMock()
        moodle.get_categories.side_effect = MoodleAPIError("err", "unknownerror")
        with pytest.raises(MoodleAPIError):
            await _ensure_root_category(moodle)
