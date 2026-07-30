"""
Pruebas unitarias para MoodleIntegration.

Verifica la capa de orquestación de alto nivel con un MoodleService mockeado.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.moodle import MoodleIntegration
from app.services.moodle_operations import MoodleService


@pytest.fixture
def moodle_integration():
    mock_service = AsyncMock(spec=MoodleService)
    return MoodleIntegration(mock_service)


class TestRelocateCategory:
    @pytest.mark.asyncio
    async def test_success(self, moodle_integration):
        integ = moodle_integration
        integ.service.update_category.return_value = {}
        result = await integ.relocate_category("CAT-01", 123, "PARENT-01")
        assert result is True
        integ.service.update_category.assert_awaited_once_with(
            category_id=123, parent_idnumber="PARENT-01",
        )

    @pytest.mark.asyncio
    async def test_overloaded_raises(self, moodle_integration):
        from app.services.moodle_errors import MoodleOverloadedError
        integ = moodle_integration
        integ.service.update_category.side_effect = ConnectionError("gateway time-out")
        with pytest.raises(MoodleOverloadedError):
            await integ.relocate_category("CAT-01", 123, "PARENT-01")

    @pytest.mark.asyncio
    async def test_error_returns_false(self, moodle_integration):
        integ = moodle_integration
        integ.service.update_category.side_effect = ValueError("invalid param")
        result = await integ.relocate_category("CAT-01", 123, "PARENT-01")
        assert result is False
        assert integ.last_error != ""


class TestDeleteCourse:
    @pytest.mark.asyncio
    async def test_success(self, moodle_integration):
        integ = moodle_integration
        integ.service.delete_courses.return_value = {"status": "ok"}
        result = await integ.delete_course("TEST-101")
        assert result is True

    @pytest.mark.asyncio
    async def test_not_found_idempotent(self, moodle_integration):
        integ = moodle_integration
        integ.service.delete_courses.return_value = None
        result = await integ.delete_course("TEST-101")
        assert result is True


class TestActivateCourse:
    @pytest.mark.asyncio
    async def test_activate_visible_course(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.return_value = [
            {"shortname": "TEST-101", "visible": 0, "id": "1"}
        ]
        integ.service.update_courses.return_value = {}
        integ.service.get_courses.return_value = [
            {"shortname": "TEST-101", "visible": 1, "id": "1"}
        ]
        result = await integ.activate_course("TEST-101")
        assert result is True

    @pytest.mark.asyncio
    async def test_course_not_found(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.return_value = []
        result = await integ.activate_course("NONEXISTENT")
        assert result is False

    @pytest.mark.asyncio
    async def test_activation_not_confirmed(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.side_effect = [
            [{"shortname": "TEST-101", "visible": 0, "id": "1"}],
            [{"shortname": "TEST-101", "visible": 0, "id": "1"}],
        ]
        result = await integ.activate_course("TEST-101")
        assert result is False


class TestHideCourse:
    @pytest.mark.asyncio
    async def test_hide_visible_course(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.return_value = [
            {"shortname": "TEST-101", "visible": 1, "id": "1"}
        ]
        integ.service.update_courses.return_value = {}
        integ.service.get_courses.return_value = [
            {"shortname": "TEST-101", "visible": 0, "id": "1"}
        ]
        result = await integ.hide_course("TEST-101")
        assert result is True

    @pytest.mark.asyncio
    async def test_course_not_found_hide(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.return_value = []
        result = await integ.hide_course("NONEXISTENT")
        assert result is False


class TestRenameCourse:
    @pytest.mark.asyncio
    async def test_rename_success(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.side_effect = [
            [],  # target not found
            [{"shortname": "OLD-NAME", "id": "1", "visible": 1}],
            [{"shortname": "NEW-NAME", "id": "1", "visible": 1}],
        ]
        result = await integ.rename_course("OLD-NAME", "NEW-NAME", "New Fullname")
        assert result is True

    @pytest.mark.asyncio
    async def test_target_already_exists(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.return_value = [{"shortname": "NEW-NAME", "id": "2"}]
        result = await integ.rename_course("OLD-NAME", "NEW-NAME", "New Fullname")
        assert result is True

    @pytest.mark.asyncio
    async def test_source_not_found(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.side_effect = [
            [],
            [],
        ]
        result = await integ.rename_course("NONEXISTENT", "NEW-NAME", "New")
        assert result is False
        assert integ.last_error != ""


class TestFindUserByEmail:
    @pytest.mark.asyncio
    async def test_found(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_users.return_value = [
            {"username": "jdoe", "email": "jdoe@test.com"}
        ]
        result = await integ.find_user_by_email("jdoe@test.com")
        assert result is not None
        assert result["username"] == "jdoe"

    @pytest.mark.asyncio
    async def test_not_found(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_users.return_value = []
        result = await integ.find_user_by_email("nobody@test.com")
        assert result is None


class TestFindUsersByEmails:
    @pytest.mark.asyncio
    async def test_found_multiple(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_users.return_value = [
            {"username": "u1", "email": "u1@test.com"},
            {"username": "u2", "email": "u2@test.com"},
        ]
        result = await integ.find_users_by_emails(["u1@test.com", "u2@test.com"])
        assert len(result) == 2
        assert "u1@test.com" in result

    @pytest.mark.asyncio
    async def test_empty_input(self, moodle_integration):
        integ = moodle_integration
        result = await integ.find_users_by_emails([])
        assert result == {}


class TestEnrolTeacher:
    @pytest.mark.asyncio
    async def test_enrol_success(self, moodle_integration):
        integ = moodle_integration
        integ.service.enrol_users.return_value = {"success": True, "enrolled": 1, "failed": 0}
        result = await integ.enrol_teacher("prof1", "CURSO-101")
        assert result["success"] is True
        assert result["reason"] == "enrolled"

    @pytest.mark.asyncio
    async def test_already_enrolled(self, moodle_integration):
        integ = moodle_integration
        integ.service.enrol_users.return_value = {
            "success": False, "enrolled": 0, "failed": 1,
            "errors": ["already enrolled"], "error_codes": ["alreadyenrolled"],
        }
        result = await integ.enrol_teacher("prof1", "CURSO-101")
        assert result["success"] is True
        assert result["reason"] == "already_enrolled"

    @pytest.mark.asyncio
    async def test_enrol_failure(self, moodle_integration):
        integ = moodle_integration
        integ.service.enrol_users.return_value = {
            "success": False, "enrolled": 0, "failed": 1,
            "errors": ["Server error"], "error_codes": [],
        }
        result = await integ.enrol_teacher("prof1", "CURSO-101")
        assert result["success"] is False


class TestIsUserActive:
    def test_active(self):
        assert MoodleIntegration.is_user_active({"suspended": "0"}) is True

    def test_suspended(self):
        assert MoodleIntegration.is_user_active({"suspended": "1"}) is False

    def test_no_field(self):
        assert MoodleIntegration.is_user_active({}) is True


class TestCreateCourse:
    @pytest.mark.asyncio
    async def test_create_new_course(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.side_effect = [
            [],  # not existing
            [{"shortname": "NEW-101", "id": "1"}],  # created
        ]
        integ.service.create_courses.return_value = [{"shortname": "NEW-101", "id": "1"}]
        result = await integ.create_course("NEW-101", "New Course", "CAT-01")
        assert result is True

    @pytest.mark.asyncio
    async def test_course_exists_skip(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.return_value = [{"shortname": "EXISTING", "id": "1"}]
        result = await integ.create_course("EXISTING", "Existing", "CAT-01")
        assert result is True

    @pytest.mark.asyncio
    async def test_creation_not_confirmed(self, moodle_integration):
        integ = moodle_integration
        integ.service.get_courses.side_effect = [
            [],  # not existing
            [],  # not confirmed after creation
        ]
        integ.service.create_courses.return_value = [{"shortname": "NEW-101", "id": "1"}]
        result = await integ.create_course("NEW-101", "New Course", "CAT-01")
        assert result is False
        assert "no fue creado" in integ.last_error


class TestCreateUserIfNotExists:
    @pytest.mark.asyncio
    async def test_non_institutional_email(self, moodle_integration):
        integ = moodle_integration
        result = await integ.create_user_if_not_exists({"email": "foo@bar.com", "cedula": "123"})
        assert result == (None, False)
        assert "no institucional" in integ.last_error
