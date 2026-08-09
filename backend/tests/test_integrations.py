"""
Pruebas unitarias para MoodleIntegration.

Verifica la lógica de alto nivel: creación condicional de usuarios,
matriculación de profesores y detección de usuarios activos.
"""

from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.integrations.moodle import MoodleIntegration
from app.services.moodle_errors import MoodleAPIError


@pytest.fixture
def integration():
    mock_service = AsyncMock()
    mock_service.get_users.return_value = []
    mock_service.get_user_by_username.return_value = None
    mock_service.create_users.return_value = [{"id": 1, "username": "testuser"}]
    mock_service.enrol_users.return_value = {
        "success": True,
        "enrolled": 1,
        "failed": 0,
        "errors": [],
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
            {"id": "2", "username": "teacher2", "email": "a@ut.edu.co", "timecreated": "200"},
            {"id": "1", "username": "teacher1", "email": "a@ut.edu.co", "timecreated": "100"},
        ]
        integration.service._request.return_value = []
        user = await integration.find_user_by_email("a@ut.edu.co")
        assert user is not None
        # La cuenta vieja (id=1) queda renombrada con el username de la nueva.
        assert user["username"] == "teacher2"
        assert user["id"] == "1"


# ---------------------------------------------------------------------------
# Consolidación de duplicados por email (conservar antigua + eliminar modernas)
# ---------------------------------------------------------------------------
class TestConsolidateDuplicates:
    @staticmethod
    def _auth_calls(calls):
        return [
            call.args[0]
            for call in calls
            if call.args and call.args[0] and "auth" in call.args[0][0]
        ]

    @staticmethod
    def _rename_calls(calls):
        return [
            call.args[0]
            for call in calls
            if call.args and call.args[0] and "username" in call.args[0][0]
        ]

    @pytest.mark.asyncio
    async def test_duplicate_sin_cursos_renombra_vieja_y_elimina_nueva(self, integration):
        integration.service.get_users.return_value = [
            {"id": "2", "username": "nuevo", "email": "a@ut.edu.co", "timecreated": "200"},
            {"id": "1", "username": "viejo", "email": "a@ut.edu.co", "timecreated": "100"},
        ]
        integration.service._request.return_value = []
        result = await integration.find_users_by_emails(["a@ut.edu.co"])
        # La cuenta vieja queda renombrada con el username de la nueva.
        assert result["a@ut.edu.co"]["username"] == "nuevo"
        assert result["a@ut.edu.co"]["id"] == "1"
        # 1) nueva -> temp libera el username, 2) vieja -> nueva
        renames = self._rename_calls(integration.service.update_users.await_args_list)
        assert renames == [
            [{"id": "2", "username": "zzdel_nuevo"}],
            [{"id": "1", "username": "nuevo"}],
        ]
        integration.service.delete_users.assert_awaited_with(["zzdel_nuevo"])
        c = integration.last_email_conflicts[0]
        assert c["renamed"] == "nuevo"
        assert c["selected"] == "nuevo"
        assert set(c["usernames"]) == {"viejo", "nuevo"}
        assert c["deleted"] == ["zzdel_nuevo"]
        assert c["pending_review"] == []

    @pytest.mark.asyncio
    async def test_duplicate_con_cursos_no_se_elimina_ni_renombra(self, integration):
        integration.service.get_users.return_value = [
            {"id": "2", "username": "nuevo", "email": "a@ut.edu.co", "timecreated": "200"},
            {"id": "1", "username": "viejo", "email": "a@ut.edu.co", "timecreated": "100"},
        ]
        integration.service._request.return_value = [{"id": 111}]
        result = await integration.find_users_by_emails(["a@ut.edu.co"])
        assert result["a@ut.edu.co"]["username"] == "viejo"
        integration.service.delete_users.assert_not_awaited()
        integration.service.update_users.assert_not_awaited()
        c = integration.last_email_conflicts[0]
        assert c["renamed"] == ""
        assert c["deleted"] == []
        assert c["pending_review"] == ["nuevo"]

    @pytest.mark.asyncio
    async def test_webservice_no_expone_cursos_no_se_elimina(self, integration):
        integration.service.get_users.return_value = [
            {"id": "2", "username": "nuevo", "email": "a@ut.edu.co", "timecreated": "200"},
            {"id": "1", "username": "viejo", "email": "a@ut.edu.co", "timecreated": "100"},
        ]
        integration.service._request.side_effect = Exception("acceso denegado")
        result = await integration.find_users_by_emails(["a@ut.edu.co"])
        assert result["a@ut.edu.co"]["username"] == "viejo"
        integration.service.delete_users.assert_not_awaited()
        c = integration.last_email_conflicts[0]
        assert c["renamed"] == ""
        assert c["deleted"] == []
        assert c["pending_review"] == ["nuevo"]

    @pytest.mark.asyncio
    async def test_mas_de_dos_elimina_recientes_sin_cursos(self, integration):
        integration.service.get_users.return_value = [
            {"id": "3", "username": "nueva", "email": "a@ut.edu.co", "timecreated": "300"},
            {"id": "2", "username": "media", "email": "a@ut.edu.co", "timecreated": "200"},
            {"id": "1", "username": "vieja", "email": "a@ut.edu.co", "timecreated": "100"},
        ]
        integration.service._request.return_value = []
        result = await integration.find_users_by_emails(["a@ut.edu.co"])
        assert result["a@ut.edu.co"]["username"] == "nueva"
        assert result["a@ut.edu.co"]["id"] == "1"
        integration.service.delete_users.assert_awaited()
        args = integration.service.delete_users.await_args.args[0]
        assert set(args) == {"media", "zzdel_nueva"}
        c = integration.last_email_conflicts[0]
        assert c["renamed"] == "nueva"
        assert set(c["deleted"]) == {"media", "zzdel_nueva"}

    @pytest.mark.asyncio
    async def test_no_se_puede_liberar_username_se_omite_rename(self, integration):
        integration.service.get_users.return_value = [
            {"id": "2", "username": "nuevo", "email": "a@ut.edu.co", "timecreated": "200"},
            {"id": "1", "username": "viejo", "email": "a@ut.edu.co", "timecreated": "100"},
        ]
        integration.service._request.return_value = []
        integration.service.update_users.side_effect = Exception("API caída")
        result = await integration.find_users_by_emails(["a@ut.edu.co"])
        assert result["a@ut.edu.co"]["username"] == "viejo"
        integration.service.delete_users.assert_awaited_with(["nuevo"])
        c = integration.last_email_conflicts[0]
        assert c["renamed"] == ""
        assert c["deleted"] == ["nuevo"]

    @pytest.mark.asyncio
    async def test_fallo_rename_antigua_hace_rollback(self, integration):
        integration.service.get_users.return_value = [
            {"id": "2", "username": "nuevo", "email": "a@ut.edu.co", "timecreated": "200"},
            {"id": "1", "username": "viejo", "email": "a@ut.edu.co", "timecreated": "100"},
        ]
        integration.service._request.return_value = []
        # 1) nueva->temp OK, 2) vieja->nueva falla, 3) rollback nueva->nueva
        integration.service.update_users.side_effect = [
            {"id": 2},
            Exception("rename falló"),
            {"id": 2},
        ]
        result = await integration.find_users_by_emails(["a@ut.edu.co"])
        assert result["a@ut.edu.co"]["username"] == "viejo"
        renames = self._rename_calls(integration.service.update_users.await_args_list)
        assert renames == [
            [{"id": "2", "username": "zzdel_nuevo"}],
            [{"id": "1", "username": "nuevo"}],
            [{"id": "2", "username": "nuevo"}],
        ]
        integration.service.delete_users.assert_awaited_with(["nuevo"])
        c = integration.last_email_conflicts[0]
        assert c["renamed"] == ""


# ---------------------------------------------------------------------------
# Paso a base de datos externa (auth manual -> db)
# ---------------------------------------------------------------------------
class TestExternalAuthSwitch:
    @staticmethod
    def _auth_calls(calls):
        return [
            call.args[0]
            for call in calls
            if call.args and call.args[0] and "auth" in call.args[0][0]
        ]

    @pytest.mark.asyncio
    async def test_institucional_manual_pasa_a_externa(self, integration):
        integration.service.get_users.return_value = [
            {
                "id": "2",
                "username": "nuevo",
                "email": "a@ut.edu.co",
                "timecreated": "200",
                "auth": "db",
            },
            {
                "id": "1",
                "username": "viejo",
                "email": "a@ut.edu.co",
                "timecreated": "100",
                "auth": "manual",
            },
        ]
        integration.service._request.return_value = []
        result = await integration.find_users_by_emails(["a@ut.edu.co"])
        assert result["a@ut.edu.co"]["username"] == "nuevo"
        auth_calls = self._auth_calls(integration.service.update_users.await_args_list)
        assert auth_calls == [[{"id": "1", "auth": "db"}]]
        c = integration.last_email_conflicts[0]
        assert c["auth_switched"] is True
        assert c["auth_reason"] == "manual->db"

    @pytest.mark.asyncio
    async def test_no_institucional_queda_en_manual(self, integration):
        integration.service.get_users.return_value = [
            {
                "id": "2",
                "username": "nuevo",
                "email": "x@gmail.com",
                "timecreated": "200",
                "auth": "manual",
            },
            {
                "id": "1",
                "username": "viejo",
                "email": "x@gmail.com",
                "timecreated": "100",
                "auth": "manual",
            },
        ]
        integration.service._request.return_value = []
        await integration.find_users_by_emails(["x@gmail.com"])
        assert self._auth_calls(integration.service.update_users.await_args_list) == []
        c = integration.last_email_conflicts[0]
        assert c["auth_switched"] is False
        assert "no institucional" in c["auth_reason"]

    @pytest.mark.asyncio
    async def test_admin_excluido_por_email_queda_en_manual(self, integration, monkeypatch):
        monkeypatch.setattr(settings, "EXTERNAL_AUTH_EXCLUDED_USERS", "hdmendieta@ut.edu.co")
        integration.service.get_users.return_value = [
            {
                "id": "2",
                "username": "nuevo",
                "email": "hdmendieta@ut.edu.co",
                "timecreated": "200",
                "auth": "manual",
            },
            {
                "id": "1",
                "username": "viejo",
                "email": "hdmendieta@ut.edu.co",
                "timecreated": "100",
                "auth": "manual",
            },
        ]
        integration.service._request.return_value = []
        await integration.find_users_by_emails(["hdmendieta@ut.edu.co"])
        assert self._auth_calls(integration.service.update_users.await_args_list) == []
        c = integration.last_email_conflicts[0]
        assert c["auth_switched"] is False
        assert "admin" in c["auth_reason"]

    @pytest.mark.asyncio
    async def test_admin_excluido_por_username_queda_en_manual(self, integration, monkeypatch):
        monkeypatch.setattr(settings, "EXTERNAL_AUTH_EXCLUDED_USERS", "ogt@ut.edu.co")
        # La reciente tiene cursos: no hay rename, el username 'ogt' es la llave de exclusión.
        integration.service.get_users.return_value = [
            {
                "id": "2",
                "username": "ogt",
                "email": "ogt@ut.edu.co",
                "timecreated": "200",
                "auth": "manual",
            },
            {
                "id": "1",
                "username": "viejo",
                "email": "ogt@ut.edu.co",
                "timecreated": "100",
                "auth": "manual",
            },
        ]
        integration.service._request.return_value = [{"id": 111}]
        await integration.find_users_by_emails(["ogt@ut.edu.co"])
        assert self._auth_calls(integration.service.update_users.await_args_list) == []
        c = integration.last_email_conflicts[0]
        assert c["auth_switched"] is False
        assert "admin" in c["auth_reason"]

    @pytest.mark.asyncio
    async def test_ya_externa_no_se_cambia(self, integration):
        integration.service.get_users.return_value = [
            {
                "id": "2",
                "username": "nuevo",
                "email": "a@ut.edu.co",
                "timecreated": "200",
                "auth": "db",
            },
            {
                "id": "1",
                "username": "viejo",
                "email": "a@ut.edu.co",
                "timecreated": "100",
                "auth": "db",
            },
        ]
        integration.service._request.return_value = []
        await integration.find_users_by_emails(["a@ut.edu.co"])
        assert self._auth_calls(integration.service.update_users.await_args_list) == []
        c = integration.last_email_conflicts[0]
        assert c["auth_switched"] is False
        assert c["auth_reason"] == "ya db"


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
            "a@ut.edu.co": {
                "id": "1",
                "username": "nuevo",
                "email": "a@ut.edu.co",
                "timecreated": "100",
            }
        }
        assert len(integration.last_email_conflicts) == 1
        c = integration.last_email_conflicts[0]
        assert c["email"] == "a@ut.edu.co"
        assert c["selected"] == "nuevo"
        assert c["renamed"] == "nuevo"
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
        # Se conserva la antigua (id=3) renombrada al username de la nueva.
        assert result["c@ut.edu.co"]["username"] == "nuevo"
        assert result["c@ut.edu.co"]["id"] == "3"

    @pytest.mark.asyncio
    async def test_grouped_emails(self, integration):
        integration.service.get_users.return_value = [
            {"id": "1", "username": "a1", "email": "a@ut.edu.co"},
            {"id": "2", "username": "a2", "email": "a@ut.edu.co"},
            {"id": "3", "username": "b1", "email": "b@ut.edu.co"},
        ]
        result = await integration.find_users_by_emails(["a@ut.edu.co", "b@ut.edu.co"])
        assert result["a@ut.edu.co"]["username"] == "a2"
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
        username, created = await integration.create_user_if_not_exists(
            {
                "email": "personal@gmail.com",
            }
        )
        assert username is None
        assert created is False

    @pytest.mark.asyncio
    async def test_existing_user_by_institutional_email(self, integration):
        integration.service.get_users.return_value = [
            {"username": "teacher1", "email": "a@ut.edu.co"}
        ]
        username, created = await integration.create_user_if_not_exists(
            {
                "email": "a@ut.edu.co",
                "firstname": "Ana",
                "lastname": "Pérez",
            }
        )
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

        username, created = await integration.create_user_if_not_exists(
            {
                "email": "institucional@ut.edu.co",
                "email_personal": "personal@gmail.com",
                "firstname": "Ana",
                "lastname": "Pérez",
            }
        )
        assert username == "teacher1"
        assert created is False

    @pytest.mark.asyncio
    async def test_new_user_created(self, integration):
        integration.service.get_users.return_value = []
        integration.service.get_user_by_username.side_effect = [
            None,  # no existe por username (lookup previo a crear)
            {"id": 10, "username": "anita"},  # verificación post-creación
        ]
        integration.service.create_users.return_value = [{"id": 10, "username": "anita"}]
        username, created = await integration.create_user_if_not_exists(
            {
                "email": "anita@ut.edu.co",
                "firstname": "Ana",
                "lastname": "Pérez",
                "cedula": "12345",
            }
        )
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
        integration.service.create_users.return_value = [{"id": 10, "username": "anita"}]
        await integration.create_user_if_not_exists(
            {
                "email": "anita@ut.edu.co",
                "firstname": "Ana",
                "lastname": "Pérez",
                "cedula": "12345",
                "city": "IBAGUE",
                "description": "Perfil docente",
            }
        )
        call_args = integration.service.create_users.call_args[0][0][0]
        assert call_args["city"] == "IBAGUE"
        assert call_args["description"] == "Perfil docente"

    @pytest.mark.asyncio
    async def test_lookup_error_returns_none(self, integration):
        integration.service.get_users.side_effect = MoodleAPIError("API down")
        username, created = await integration.create_user_if_not_exists(
            {
                "email": "anita@ut.edu.co",
            }
        )
        assert username is None
        assert created is False

    @pytest.mark.asyncio
    async def test_creation_error_returns_none(self, integration):
        integration.service.get_users.return_value = []
        integration.service.create_users.side_effect = MoodleAPIError("Duplicate")
        username, created = await integration.create_user_if_not_exists(
            {
                "email": "anita@ut.edu.co",
                "firstname": "Ana",
                "lastname": "Pérez",
            }
        )
        assert username is None
        assert created is False

    @pytest.mark.asyncio
    async def test_new_user_auth_manual_warning_on_non_manual(self, integration, caplog):
        integration.service.get_users.return_value = []
        integration.service.get_user_by_username.side_effect = [
            None,
            {"id": 10, "username": "anita", "auth": "db"},
        ]
        integration.service.create_users.return_value = [{"id": 10, "username": "anita"}]
        import logging

        with caplog.at_level(logging.WARNING, logger="app.integrations.moodle"):
            username, created = await integration.create_user_if_not_exists(
                {
                    "email": "anita@ut.edu.co",
                    "firstname": "Ana",
                    "lastname": "Pérez",
                    "cedula": "12345",
                }
            )
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
            "success": False,
            "enrolled": 0,
            "failed": 1,
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
            "success": False,
            "enrolled": 0,
            "failed": 1,
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
