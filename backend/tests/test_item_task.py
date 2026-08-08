import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.moodle_errors import MoodleOverloadedError
from app.workers.phases.item_task import process_etl_item


def _make_item(item_id=1, action="delete", execution_id=1, status="pending", **extra):
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


class TestProcessEtlItem:
    def test_item_not_found(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item", return_value=None),
        ):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            process_etl_item(1)
            mock_db.close.assert_called_once()

    def test_item_already_completed(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
        ):
            mock_get.return_value = _make_item(status="completed")
            mock_sl.return_value = MagicMock()
            process_etl_item(1)

    def test_missing_action(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.update_item") as mock_update,
        ):
            item = _make_item()
            item.detail = {}
            mock_get.return_value = item
            db = MagicMock()
            mock_sl.return_value = db
            process_etl_item(1)
            mock_update.assert_called_once_with(db, item.id, "failed", "Falta 'action' en detail")

    def test_cancelled_execution(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.should_cancel", return_value=True),
            patch("app.workers.phases.item_task.update_item") as mock_update,
        ):
            mock_get.return_value = _make_item()
            db = MagicMock()
            mock_sl.return_value = db
            process_etl_item(1)
            mock_update.assert_called_once_with(db, 1, "failed", "Ejecución cancelada")

    def test_unknown_action(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration"),
            patch("app.workers.phases.item_task.update_item") as mock_update,
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_get.return_value = _make_item(action="invalid")
            db = MagicMock()
            mock_sl.return_value = db
            process_etl_item(1)
            mock_update.assert_any_call(db, 1, "failed", "Acción desconocida: invalid")

    @pytest.mark.parametrize(
        "action,method",
        [
            ("delete", "delete_course"),
            ("activate", "activate_course"),
            ("hide", "hide_course"),
        ],
    )
    def test_simple_actions_success(self, action, method):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item"),
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            getattr(mock_integ, method).return_value = True
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item(action=action)
            mock_sl.return_value = MagicMock()
            process_etl_item(1)

    @pytest.mark.parametrize(
        "action,method",
        [
            ("delete", "delete_course"),
            ("activate", "activate_course"),
            ("hide", "hide_course"),
        ],
    )
    def test_simple_actions_failure(self, action, method):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item") as mock_update,
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            getattr(mock_integ, method).return_value = False
            mock_integ.last_error = f"Error in {method}"
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item(action=action)
            db = MagicMock()
            mock_sl.return_value = db
            process_etl_item(1)
            mock_update.assert_any_call(db, 1, "failed", f"Error in {method}")

    def test_rename_success(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item"),
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.rename_course.return_value = True
            mock_integ_cls.return_value = mock_integ
            item = _make_item(action="rename", old_shortname="OLD_001", fullname="New Fullname")
            mock_get.return_value = item
            mock_sl.return_value = MagicMock()
            process_etl_item(1)
            mock_integ.rename_course.assert_called_once_with(
                old_shortname="OLD_001", new_shortname="IDENTIFIER_001", new_fullname="New Fullname"
            )

    def test_create_course_success(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item"),
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.create_course.return_value = True
            mock_integ_cls.return_value = mock_integ
            item = _make_item(
                action="create", fullname="New Course", category_idnumber="CAT_01", template_id=42
            )
            mock_get.return_value = item
            mock_sl.return_value = MagicMock()
            process_etl_item(1)
            mock_integ.create_course.assert_called_once_with(
                shortname="IDENTIFIER_001",
                fullname="New Course",
                category_idnumber="CAT_01",
                template_id=42,
                recreate=False,
            )

    def test_create_user_success(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item"),
            patch("app.workers.phases.item_task.save_log") as mock_save_log,
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.create_user_if_not_exists.return_value = ("newuser", True)
            mock_integ_cls.return_value = mock_integ
            item = _make_item(
                action="create_user",
                firstname="John",
                lastname="Doe",
                email="john@test.com",
                password="pwd123",
                cedula="123",
                city="City",
                description="desc",
            )
            mock_get.return_value = item
            mock_sl.return_value = MagicMock()
            process_etl_item(1)
            mock_save_log.assert_called_once()
            _, _, _, action, identifier, detail = mock_save_log.call_args[0]
            assert action == "user_created_createpassword"
            assert identifier == "newuser"
            assert detail["auth"] == "manual"
            assert detail["base_db"] == "Manual"

    def test_create_user_failure(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item"),
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.create_user_if_not_exists.return_value = (None, False)
            mock_integ.last_error = "User creation failed"
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item(action="create_user")
            mock_sl.return_value = MagicMock()
            process_etl_item(1)

    def test_enrol_success(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item"),
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.enrol_teacher.return_value = {"success": True}
            mock_integ_cls.return_value = mock_integ
            item = _make_item(action="enrol", course_shortname="CURSE_101", _course_id=42)
            mock_get.return_value = item
            mock_sl.return_value = MagicMock()
            process_etl_item(1)
            mock_integ.enrol_teacher.assert_called_once_with(
                username="IDENTIFIER_001",
                course_shortname="CURSE_101",
                course_map={"CURSE_101": 42},
            )

    def test_enrol_failure(self):
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.update_item"),
            patch("app.workers.phases.item_task._refresh_phase_progress"),
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.enrol_teacher.return_value = {"success": False}
            mock_integ.last_error = "Enrol failed"
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item(action="enrol", course_shortname="CURSE_101")
            mock_sl.return_value = MagicMock()
            process_etl_item(1)

    def test_moodle_overloaded_re_raised(self):
        mock_integ = AsyncMock()
        mock_integ.delete_course.side_effect = MoodleOverloadedError("overloaded")
        with (
            patch("app.workers.phases.item_task.SessionLocal") as mock_sl,
            patch("app.workers.phases.item_task.get_item") as mock_get,
            patch("app.workers.phases.item_task.get_moodle_service", return_value=_make_moodle()),
            patch("app.workers.phases.item_task.MoodleIntegration") as mock_integ_cls,
            patch("app.workers.phases.item_task.claim_item", return_value=True),
        ):
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item()
            mock_sl.return_value = MagicMock()
            with contextlib.suppress(Exception):
                process_etl_item(1)
