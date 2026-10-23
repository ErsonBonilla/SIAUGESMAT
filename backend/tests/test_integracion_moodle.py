"""
Pruebas unitarias para MoodleIntegration.

Verifica la capa de orquestación de alto nivel con un MoodleService mockeado.
"""

from unittest.mock import AsyncMock

import pytest

from app.integrations.integracion_moodle import IntegracionMoodle
from app.services.operaciones_moodle import ServicioMoodle


@pytest.fixture
def moodle_integration():
    mock_service = AsyncMock(spec=ServicioMoodle)
    return IntegracionMoodle(mock_service)


class TestRelocateCategory:
    @pytest.mark.asyncio
    async def test_success(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.actualizar_categoria.return_value = {}
        result = await integ.reubicar_categoria("CAT-01", 123, "PARENT-01")
        assert result is True
        integ.servicio.actualizar_categoria.assert_awaited_once_with(
            category_id=123,
            parent_idnumber="PARENT-01",
        )

    @pytest.mark.asyncio
    async def test_overloaded_raises(self, moodle_integration):
        from app.services.errores_moodle import ErrorMoodleSobrecargado

        integ = moodle_integration
        integ.servicio.actualizar_categoria.side_effect = ConnectionError("gateway time-out")
        with pytest.raises(ErrorMoodleSobrecargado):
            await integ.reubicar_categoria("CAT-01", 123, "PARENT-01")

    @pytest.mark.asyncio
    async def test_error_returns_false(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.actualizar_categoria.side_effect = ValueError("invalid param")
        result = await integ.reubicar_categoria("CAT-01", 123, "PARENT-01")
        assert result is False
        assert integ.ultimo_error != ""


class TestDeleteCourse:
    @pytest.mark.asyncio
    async def test_success(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.eliminar_cursos.return_value = {"status": "ok"}
        result = await integ.eliminar_curso("TEST-101")
        assert result is True

    @pytest.mark.asyncio
    async def test_not_found_idempotent(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.eliminar_cursos.return_value = None
        result = await integ.eliminar_curso("TEST-101")
        assert result is True


class TestActivateCourse:
    @pytest.mark.asyncio
    async def test_activate_visible_course(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.return_value = [
            {"shortname": "TEST-101", "visible": 0, "id": "1"}
        ]
        integ.servicio.actualizar_cursos.return_value = {}
        integ.servicio.obtener_cursos.return_value = [
            {"shortname": "TEST-101", "visible": 1, "id": "1"}
        ]
        result = await integ.activar_curso("TEST-101")
        assert result is True

    @pytest.mark.asyncio
    async def test_course_not_found(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.return_value = []
        result = await integ.activar_curso("NONEXISTENT")
        assert result is False

    @pytest.mark.asyncio
    async def test_activation_not_confirmed(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.side_effect = [
            [{"shortname": "TEST-101", "visible": 0, "id": "1"}],
            [{"shortname": "TEST-101", "visible": 0, "id": "1"}],
        ]
        result = await integ.activar_curso("TEST-101")
        assert result is False


class TestHideCourse:
    @pytest.mark.asyncio
    async def test_hide_visible_course(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.return_value = [
            {"shortname": "TEST-101", "visible": 1, "id": "1"}
        ]
        integ.servicio.actualizar_cursos.return_value = {}
        integ.servicio.obtener_cursos.return_value = [
            {"shortname": "TEST-101", "visible": 0, "id": "1"}
        ]
        result = await integ.ocultar_curso("TEST-101")
        assert result is True

    @pytest.mark.asyncio
    async def test_course_not_found_hide(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.return_value = []
        result = await integ.ocultar_curso("NONEXISTENT")
        assert result is False


class TestRenameCourse:
    @pytest.mark.asyncio
    async def test_rename_success(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.side_effect = [
            [],  # target not found
            [{"shortname": "OLD-NAME", "id": "1", "visible": 1}],
            [{"shortname": "NEW-NAME", "id": "1", "visible": 1}],
        ]
        result = await integ.renombrar_curso("OLD-NAME", "NEW-NAME", "New Fullname")
        assert result is True

    @pytest.mark.asyncio
    async def test_target_already_exists(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.return_value = [{"shortname": "NEW-NAME", "id": "2"}]
        result = await integ.renombrar_curso("OLD-NAME", "NEW-NAME", "New Fullname")
        assert result is True

    @pytest.mark.asyncio
    async def test_source_not_found(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.side_effect = [
            [],
            [],
        ]
        result = await integ.renombrar_curso("NONEXISTENT", "NEW-NAME", "New")
        assert result is False
        assert integ.ultimo_error != ""


class TestFindUserByEmail:
    @pytest.mark.asyncio
    async def test_found(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_usuarios.return_value = [
            {"username": "jdoe", "email": "jdoe@test.com"}
        ]
        result = await integ.encontrar_usuario_por_correo("jdoe@test.com")
        assert result is not None
        assert result["username"] == "jdoe"

    @pytest.mark.asyncio
    async def test_not_found(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_usuarios.return_value = []
        result = await integ.encontrar_usuario_por_correo("nobody@test.com")
        assert result is None


class TestFindUsersByEmails:
    @pytest.mark.asyncio
    async def test_found_multiple(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_usuarios.return_value = [
            {"username": "u1", "email": "u1@test.com"},
            {"username": "u2", "email": "u2@test.com"},
        ]
        result = await integ.encontrar_usuarios_por_correos(["u1@test.com", "u2@test.com"])
        assert len(result) == 2
        assert "u1@test.com" in result

    @pytest.mark.asyncio
    async def test_empty_input(self, moodle_integration):
        integ = moodle_integration
        result = await integ.encontrar_usuarios_por_correos([])
        assert result == {}


class TestEnrolTeacher:
    @pytest.mark.asyncio
    async def test_enrol_success(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.matricular_usuarios.return_value = {
            "success": True,
            "enrolled": 1,
            "failed": 0,
        }
        result = await integ.matricular_docente("prof1", "CURSO-101")
        assert result["success"] is True
        assert result["reason"] == "enrolled"

    @pytest.mark.asyncio
    async def test_already_enrolled(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.matricular_usuarios.return_value = {
            "success": False,
            "enrolled": 0,
            "failed": 1,
            "errors": ["already enrolled"],
            "error_codes": ["alreadyenrolled"],
        }
        result = await integ.matricular_docente("prof1", "CURSO-101")
        assert result["success"] is True
        assert result["reason"] == "already_enrolled"

    @pytest.mark.asyncio
    async def test_enrol_failure(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.matricular_usuarios.return_value = {
            "success": False,
            "enrolled": 0,
            "failed": 1,
            "errors": ["Server error"],
            "error_codes": [],
        }
        result = await integ.matricular_docente("prof1", "CURSO-101")
        assert result["success"] is False


class TestIsUserActive:
    def test_active(self):
        assert IntegracionMoodle.es_usuario_activo({"suspended": "0"}) is True

    def test_suspended(self):
        assert IntegracionMoodle.es_usuario_activo({"suspended": "1"}) is False

    def test_no_field(self):
        assert IntegracionMoodle.es_usuario_activo({}) is True


class TestCreateCourse:
    @pytest.mark.asyncio
    async def test_create_new_course(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.side_effect = [
            [],  # not existing
            [{"shortname": "NEW-101", "id": "1"}],  # created
        ]
        integ.servicio.crear_cursos.return_value = [{"shortname": "NEW-101", "id": "1"}]
        result = await integ.crear_curso("NEW-101", "New Course", "CAT-01")
        assert result is True

    @pytest.mark.asyncio
    async def test_course_exists_skip(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.return_value = [{"shortname": "EXISTING", "id": "1"}]
        result = await integ.crear_curso("EXISTING", "Existing", "CAT-01")
        assert result is True

    @pytest.mark.asyncio
    async def test_creation_not_confirmed(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.side_effect = [
            [],  # not existing
            [],  # not confirmed after creation
        ]
        integ.servicio.crear_cursos.return_value = [{"shortname": "NEW-101", "id": "1"}]
        result = await integ.crear_curso("NEW-101", "New Course", "CAT-01")
        assert result is False
        assert "no fue creado" in integ.ultimo_error


class TestCreateUserIfNotExists:
    @pytest.mark.asyncio
    async def test_non_institutional_email(self, moodle_integration):
        integ = moodle_integration
        result = await integ.crear_usuario_si_no_existe({"email": "foo@bar.com", "cedula": "123"})
        assert result == (None, False)
        assert "no institucional" in integ.ultimo_error
