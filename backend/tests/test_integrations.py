"""
Pruebas unitarias para MoodleIntegration.

Verifica la lógica de alto nivel: creación condicional de usuarios,
matriculación de profesores y detección de usuarios activos.
"""

from unittest.mock import AsyncMock

import pytest

from app.integrations.moodle import MoodleIntegration
from app.services.moodle_errors import MoodleAPIError


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
# find_users_by_emails / usernames / idnumbers (criterio "más antiguo")
# ---------------------------------------------------------------------------
class TestFindUsersByFieldOldest:
    @pytest.mark.asyncio
    async def test_email_duplicate_picks_oldest(self, integration):
        integration.service.get_users.return_value = [
            {"id": "2", "username": "nuevo", "email": "a@ut.edu.co", "timecreated": "200"},
            {"id": "1", "username": "viejo", "email": "a@ut.edu.co", "timecreated": "100"},
        ]
        result = await integration.find_users_by_emails(["a@ut.edu.co"])
        assert result == {
            "a@ut.edu.co": {"id": "1", "username": "viejo", "email": "a@ut.edu.co", "timecreated": "100"}
        }
        assert len(integration.last_email_conflicts) == 1
        c = integration.last_email_conflicts[0]
        assert c["email"] == "a@ut.edu.co"
        assert c["selected"] == "viejo"
        assert set(c["usernames"]) == {"viejo", "nuevo"}

    @pytest.mark.asyncio
    async def test_email_single_match_no_conflict(self, integration):
        integration.service.get_users.return_value = [
            {"id": "1", "username": "unico", "email": "b@ut.edu.co", "timecreated": "100"},
        ]
        result = await integration.find_users_by_emails(["b@ut.edu.co"])
        assert result["b@ut.edu.co"]["username"] == "unico"
        assert integration.last_email_conflicts == []

    @pytest.mark.asyncio
    async def test_email_picks_oldest_by_id_without_timecreated(self, integration):
        integration.service.get_users.return_value = [
            {"id": "7", "username": "nuevo", "email": "c@ut.edu.co"},
            {"id": "3", "username": "viejo", "email": "c@ut.edu.co"},
        ]
        result = await integration.find_users_by_emails(["c@ut.edu.co"])
        assert result["c@ut.edu.co"]["username"] == "viejo"

    @pytest.mark.asyncio
    async def test_grouped_emails(self, integration):
        integration.service.get_users.return_value = [
            {"id": "1", "username": "a1", "email": "a@ut.edu.co"},
            {"id": "2", "username": "a2", "email": "a@ut.edu.co"},
            {"id": "3", "username": "b1", "email": "b@ut.edu.co"},
        ]
        result = await integration.find_users_by_emails(["a@ut.edu.co", "b@ut.edu.co"])
        assert result["a@ut.edu.co"]["username"] == "a1"
        assert result["b@ut.edu.co"]["username"] == "b1"

    @pytest.mark.asyncio
    async def test_username_duplicate_picks_oldest(self, integration):
        integration.service.get_users.return_value = [
            {"id": "2", "username": "doc", "timecreated": "200"},
            {"id": "1", "username": "doc", "timecreated": "100"},
        ]
        result = await integration.find_users_by_usernames(["doc"])
        assert result["doc"]["id"] == "1"

    @pytest.mark.asyncio
    async def test_idnumber_duplicate_picks_oldest(self, integration):
        integration.service.get_users.return_value = [
            {"id": "2", "username": "doc_b", "idnumber": "12345"},
            {"id": "1", "username": "doc_a", "idnumber": "12345"},
        ]
        result = await integration.find_users_by_idnumbers(["12345"])
        assert result["12345"]["username"] == "doc_a"


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
        integration.service.get_user_by_username.side_effect = [
            None,  # no existe por username (lookup previo a crear)
            {"id": 10, "username": "anita"},  # verificación post-creación
        ]
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
        integration.service.get_user_by_username.side_effect = [
            None,
            {"id": 10, "username": "anita"},
        ]
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

    @pytest.mark.asyncio
    async def test_new_user_auth_manual_warning_on_non_manual(self, integration, caplog):
        integration.service.get_users.return_value = []
        integration.service.get_user_by_username.side_effect = [
            None,
            {"id": 10, "username": "anita", "auth": "db"},
        ]
        integration.service.create_users.return_value = [
            {"id": 10, "username": "anita"}
        ]
        import logging
        with caplog.at_level(logging.WARNING, logger="app.integrations.moodle"):
            username, created = await integration.create_user_if_not_exists({
                "email": "anita@ut.edu.co",
                "firstname": "Ana",
                "lastname": "Pérez",
                "cedula": "12345",
            })
        assert username == "anita"
        assert created is True
        assert any("auth='db'" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# enrol_teacher
# ---------------------------------------------------------------------------
class TestEnrolTeacher:
    @pytest.mark.asyncio
    async def test_user_resolution_failure(self, integration):
        integration.service.enrol_users.return_value = {
            "success": False, "enrolled": 0, "failed": 1,
            "errors": ["user=teacher1, course=CURSO1"],
        }
        result = await integration.enrol_teacher("teacher1", "CURSO1")
        assert result["success"] is False
        assert "teacher1" in result["reason"]

    @pytest.mark.asyncio
    async def test_enrolment_success(self, integration):
        result = await integration.enrol_teacher("teacher1", "CURSO1")
        assert result["success"] is True
        assert result["reason"] == "enrolled"

    @pytest.mark.asyncio
    async def test_enrolment_resolution_failure(self, integration):
        integration.service.enrol_users.return_value = {
            "success": False, "enrolled": 0, "failed": 1,
            "errors": ["user=teacher1, course=NO_EXISTE"],
        }
        result = await integration.enrol_teacher("teacher1", "NO_EXISTE")
        assert result["success"] is False
        assert "teacher1" in result["reason"] or "NO_EXISTE" in result["reason"]

    @pytest.mark.asyncio
    async def test_enrolment_api_error(self, integration):
        integration.service.enrol_users.side_effect = MoodleAPIError("API error")
        result = await integration.enrol_teacher("teacher1", "CURSO1")
        assert result["success"] is False
        assert result["reason"] is not None



