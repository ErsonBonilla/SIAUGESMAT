"""
Pruebas unitarias de los adaptadores de versión Moodle (Moodle3Adapter
y MoodleAdapterFactory).
"""

import pytest

from app.services.adaptador_moodle import (
    AdaptadorMoodle3,
    FabricaAdaptadorMoodle,
    rol_shortname_a_id,
)


# ---------------------------------------------------------------------------
# role_shortname_to_id
# ---------------------------------------------------------------------------
class TestRoleShortnameToId:
    def test_known_roles(self):
        assert rol_shortname_a_id("student") == 5
        assert rol_shortname_a_id("editingteacher") == 3
        assert rol_shortname_a_id("teacher") == 4
        assert rol_shortname_a_id("manager") == 1

    def test_unknown_role_defaults_to_student(self):
        assert rol_shortname_a_id("nonexistent") == 5

        # ---------------------------------------------------------------------------
        # Helper para crear un call_ws simulado
        # ---------------------------------------------------------------------------


def _make_call_ws(responses: dict):
    """Crea un call_ws async que devuelve respuestas según el wsfunction."""

    async def llamar_ws(wsfunction: str, params: dict):
        if wsfunction in responses:
            return responses[wsfunction]
        raise ValueError(f"Unexpected wsfunction: {wsfunction}")

    return llamar_ws

    # ===========================================================================
    # Moodle3Adapter
    # ===========================================================================


class TestMoodle3Adapter:
    @pytest.fixture
    def adapter(self):
        return AdaptadorMoodle3()

    @pytest.mark.asyncio
    async def test_enable_self_enrolment_existing(self, adapter):
        """3.x: si existe self-enrolment, retorna la instancia."""
        llamar_ws = _make_call_ws(
            {
                "core_enrol_get_course_enrolment_methods": [
                    {"type": "manual", "id": 1},
                    {"type": "self", "id": 42},
                ],
            }
        )
        result = await adapter.habilitar_automatriculacion(500, llamar_ws)
        assert result["id"] == 42
        assert result["type"] == "self"

    @pytest.mark.asyncio
    async def test_enable_self_enrolment_missing_raises(self, adapter):
        """3.x: si no existe self-enrolment, lanza excepción."""
        llamar_ws = _make_call_ws(
            {
                "core_enrol_get_course_enrolment_methods": [
                    {"type": "manual", "id": 1},
                ],
            }
        )
        with pytest.raises(ValueError, match="Método de matriculación 'self' no encontrado"):
            await adapter.habilitar_automatriculacion(500, llamar_ws)

    @pytest.mark.asyncio
    async def test_get_courses_bare(self, adapter):
        """3.x: llama core_course_get_courses sin filtros."""
        recorded = []

        async def llamar_ws(wsfunction, params):
            recorded.append((wsfunction, params))
            return []

        await adapter.obtener_cursos(None, llamar_ws)
        ws, _ = recorded[0]
        assert ws == "core_course_get_courses"

    @pytest.mark.asyncio
    async def test_get_courses_with_shortname(self, adapter):
        """3.x: usa core_course_get_courses_by_field cuando hay shortname."""
        recorded = []

        async def llamar_ws(wsfunction, params):
            recorded.append((wsfunction, params))
            return []

        await adapter.obtener_cursos("TEST101", llamar_ws)
        ws, params = recorded[0]
        assert ws == "core_course_get_courses_by_field"
        assert params["field"] == "shortname"
        assert params["value"] == "TEST101"

    def test_build_create_course_enrolment_params(self, adapter):
        """3.x: no agrega params de enrolment (no son parametros API estandar)."""
        params = {}
        course = {"enrolment_1": "self", "enrolment_1_role": "student"}
        adapter.construir_parametros_matriculacion_curso(params, course, 0)
        assert params == {}  # no-op en Moodle 3.x real

    def test_build_create_course_enrolment_params_skips_when_missing(self, adapter):
        params = {}
        adapter.construir_parametros_matriculacion_curso(params, {}, 0)
        assert params == {}

        # ===========================================================================
        # MoodleAdapterFactory
        # ===========================================================================


class TestMoodleAdapterFactory:
    def test_exact_match_3_9(self):
        adapter = FabricaAdaptadorMoodle.crear("3.9")
        assert isinstance(adapter, AdaptadorMoodle3)

    def test_exact_match_3_8(self):
        adapter = FabricaAdaptadorMoodle.crear("3.8")
        assert isinstance(adapter, AdaptadorMoodle3)

    def test_unsupported_version_raises(self):
        with pytest.raises(ValueError, match="no soportada"):
            FabricaAdaptadorMoodle.crear("2.7")

    def test_unsupported_5x_raises(self):
        with pytest.raises(ValueError, match="no soportada"):
            FabricaAdaptadorMoodle.crear("5.2")
