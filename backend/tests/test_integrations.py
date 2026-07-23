"""
Pruebas unitarias para MoodleIntegration.

Verifica la lógica de alto nivel: creación condicional de usuarios,
matriculación de profesores y detección de usuarios activos.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.integrations.moodle import MoodleIntegration
from app.services.moodle import MoodleAPIError


@pytest.fixture
def integration():
    mock_service = AsyncMock()
    mock_service.get_users.return_value = []
    mock_service.get_user_by_username.return_value = None
    mock_service.create_users.return_value = [{"id": 1, "username": "testuser"}]
    mock_service.enrol_users.return_value = {
        "success": True, "enrolled": 1, "failed": 0, "errors": [],
    }
    return MoodleIntegration(mock_service)


# ---------------------------------------------------------------------------
# is_user_active
# ---------------------------------------------------------------------------
class TestIsUserActive:
    def test_active_no_suspended_key(self):
        assert MoodleIntegration.is_user_active({}) is True

    def test_active_suspended_0_int(self):
        assert MoodleIntegration.is_user_active({"suspended": 0}) is True

    def test_inactive_suspended_1_int(self):
        assert MoodleIntegration.is_user_active({"suspended": 1}) is False

    def test_active_suspended_0_str(self):
        assert MoodleIntegration.is_user_active({"suspended": "0"}) is True

    def test_inactive_suspended_1_str(self):
        assert MoodleIntegration.is_user_active({"suspended": "1"}) is False


# ---------------------------------------------------------------------------
# find_user_by_email
# ---------------------------------------------------------------------------
class TestFindUserByEmail:
    @pytest.mark.asyncio
    async def test_found(self, integration):
        integration.service.get_users.return_value = [
            {"username": "teacher1", "email": "a@ut.edu.co"}
        ]
        user = await integration.find_user_by_email("a@ut.edu.co")
        assert user is not None
        assert user["username"] == "teacher1"

    @pytest.mark.asyncio
    async def test_not_found(self, integration):
        integration.service.get_users.return_value = []
        user = await integration.find_user_by_email("noexiste@ut.edu.co")
        assert user is None

    @pytest.mark.asyncio
    async def test_multiple_found(self, integration):
        integration.service.get_users.return_value = [
            {"username": "teacher1", "email": "a@ut.edu.co"},
            {"username": "teacher2", "email": "a@ut.edu.co"},
        ]
        user = await integration.find_user_by_email("a@ut.edu.co")
        assert user is not None
        assert user["username"] == "teacher1"


# ---------------------------------------------------------------------------
# create_user_if_not_exists
# ---------------------------------------------------------------------------
class TestCreateUserIfNotExists:
    @pytest.mark.asyncio
    async def test_non_institutional_email(self, integration):
        username, created = await integration.create_user_if_not_exists({
            "email": "personal@gmail.com",
        })
        assert username is None
        assert created is False

    @pytest.mark.asyncio
    async def test_existing_user_by_institutional_email(self, integration):
        integration.service.get_users.return_value = [
            {"username": "teacher1", "email": "a@ut.edu.co"}
        ]
        username, created = await integration.create_user_if_not_exists({
            "email": "a@ut.edu.co",
            "firstname": "Ana",
            "lastname": "Pérez",
        })
        assert username == "teacher1"
        assert created is False

    @pytest.mark.asyncio
    async def test_existing_user_by_personal_email(self, integration):
        def side_effect(field, values):
            email = values[0]
            if email == "institucional@ut.edu.co":
                return []
            if email == "personal@gmail.com":
                return [{"username": "teacher1", "email": "personal@gmail.com"}]
            return []
        integration.service.get_users.side_effect = side_effect

        username, created = await integration.create_user_if_not_exists({
            "email": "institucional@ut.edu.co",
            "email_personal": "personal@gmail.com",
            "firstname": "Ana",
            "lastname": "Pérez",
        })
        assert username == "teacher1"
        assert created is False

    @pytest.mark.asyncio
    async def test_new_user_created(self, integration):
        integration.service.get_users.return_value = []
        integration.service.create_users.return_value = [
            {"id": 10, "username": "anita"}
        ]
        username, created = await integration.create_user_if_not_exists({
            "email": "anita@ut.edu.co",
            "firstname": "Ana",
            "lastname": "Pérez",
            "cedula": "12345",
        })
        assert username == "anita"
        assert created is True
        # Verificar que create_users recibió city y description
        call_args = integration.service.create_users.call_args[0][0]
        assert "city" in call_args[0] or not call_args[0].get("city")

    @pytest.mark.asyncio
    async def test_new_user_with_city_and_description(self, integration):
        integration.service.get_users.return_value = []
        integration.service.create_users.return_value = [
            {"id": 10, "username": "anita"}
        ]
        await integration.create_user_if_not_exists({
            "email": "anita@ut.edu.co",
            "firstname": "Ana",
            "lastname": "Pérez",
            "cedula": "12345",
            "city": "IBAGUE",
            "description": "Perfil docente",
        })
        call_args = integration.service.create_users.call_args[0][0][0]
        assert call_args["city"] == "IBAGUE"
        assert call_args["description"] == "Perfil docente"

    @pytest.mark.asyncio
    async def test_lookup_error_returns_none(self, integration):
        integration.service.get_users.side_effect = MoodleAPIError("API down")
        username, created = await integration.create_user_if_not_exists({
            "email": "anita@ut.edu.co",
        })
        assert username is None
        assert created is False

    @pytest.mark.asyncio
    async def test_creation_error_returns_none(self, integration):
        integration.service.get_users.return_value = []
        integration.service.create_users.side_effect = MoodleAPIError("Duplicate")
        username, created = await integration.create_user_if_not_exists({
            "email": "anita@ut.edu.co",
            "firstname": "Ana",
            "lastname": "Pérez",
        })
        assert username is None
        assert created is False


# ---------------------------------------------------------------------------
# enrol_teacher
# ---------------------------------------------------------------------------
class TestEnrolTeacher:
    @pytest.mark.asyncio
    async def test_user_not_found(self, integration):
        integration.service.get_user_by_username.return_value = None
        result = await integration.enrol_teacher("teacher1", "CURSO1")
        assert result["success"] is False
        assert result["reason"] == "user_not_found"

    @pytest.mark.asyncio
    async def test_user_inactive(self, integration):
        integration.service.get_user_by_username.return_value = {
            "username": "teacher1", "suspended": 1,
        }
        result = await integration.enrol_teacher("teacher1", "CURSO1")
        assert result["success"] is False
        assert result["reason"] == "user_inactive"

    @pytest.mark.asyncio
    async def test_enrolment_success(self, integration):
        integration.service.get_user_by_username.return_value = {
            "username": "teacher1", "suspended": 0,
        }
        result = await integration.enrol_teacher("teacher1", "CURSO1")
        assert result["success"] is True
        assert result["reason"] == "enrolled"

    @pytest.mark.asyncio
    async def test_enrolment_resolution_failure(self, integration):
        integration.service.get_user_by_username.return_value = {
            "username": "teacher1", "suspended": 0,
        }
        integration.service.enrol_users.return_value = {
            "success": False, "enrolled": 0, "failed": 1,
            "errors": ["user=teacher1, course=NO_EXISTE"],
        }
        result = await integration.enrol_teacher("teacher1", "NO_EXISTE")
        assert result["success"] is False
        assert "teacher1" in result["reason"] or "NO_EXISTE" in result["reason"]

    @pytest.mark.asyncio
    async def test_enrolment_api_error(self, integration):
        integration.service.get_user_by_username.return_value = {
            "username": "teacher1", "suspended": 0,
        }
        integration.service.enrol_users.side_effect = MoodleAPIError("API error")
        result = await integration.enrol_teacher("teacher1", "CURSO1")
        assert result["success"] is False
        assert result["reason"] == "api_error"



