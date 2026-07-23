"""
Pruebas unitarias de los adaptadores de versión Moodle (Moodle3Adapter
y MoodleAdapterFactory).
"""

import pytest
from unittest.mock import AsyncMock

from app.services.moodle_adapter import (
    Moodle3Adapter,
    MoodleAdapterFactory,
    role_shortname_to_id,
)


# ---------------------------------------------------------------------------
# role_shortname_to_id
# ---------------------------------------------------------------------------
class TestRoleShortnameToId:
    def test_known_roles(self):
        assert role_shortname_to_id("student") == 5
        assert role_shortname_to_id("editingteacher") == 3
        assert role_shortname_to_id("teacher") == 4
        assert role_shortname_to_id("manager") == 1

    def test_unknown_role_defaults_to_student(self):
        assert role_shortname_to_id("nonexistent") == 5


# ---------------------------------------------------------------------------
# Helper para crear un call_ws simulado
# ---------------------------------------------------------------------------
def _make_call_ws(responses: dict):
    """Crea un call_ws async que devuelve respuestas según el wsfunction."""
    async def call_ws(wsfunction: str, params: dict):
        if wsfunction in responses:
            return responses[wsfunction]
        raise ValueError(f"Unexpected wsfunction: {wsfunction}")
    return call_ws


# ===========================================================================
# Moodle3Adapter
# ===========================================================================
class TestMoodle3Adapter:
    @pytest.fixture
    def adapter(self):
        return Moodle3Adapter()

    @pytest.mark.asyncio
    async def test_enable_self_enrolment_existing(self, adapter):
        """3.x: si existe self-enrolment, retorna la instancia."""
        call_ws = _make_call_ws({
            "core_enrol_get_course_enrolment_methods": [
                {"type": "manual", "id": 1},
                {"type": "self", "id": 42},
            ],
        })
        result = await adapter.enable_self_enrolment(500, call_ws)
        assert result["id"] == 42
        assert result["type"] == "self"

    @pytest.mark.asyncio
    async def test_enable_self_enrolment_missing_raises(self, adapter):
        """3.x: si no existe self-enrolment, lanza excepción."""
        call_ws = _make_call_ws({
            "core_enrol_get_course_enrolment_methods": [
                {"type": "manual", "id": 1},
            ],
        })
        with pytest.raises(ValueError, match="Enrolment .self. no encontrado"):
            await adapter.enable_self_enrolment(500, call_ws)

    @pytest.mark.asyncio
    async def test_get_courses_bare(self, adapter):
        """3.x: llama core_course_get_courses sin filtros."""
        recorded = []

        async def call_ws(wsfunction, params):
            recorded.append((wsfunction, params))
            return []

        await adapter.get_courses(None, call_ws)
        ws, _ = recorded[0]
        assert ws == "core_course_get_courses"

    @pytest.mark.asyncio
    async def test_get_courses_with_shortname(self, adapter):
        """3.x: usa core_course_get_courses_by_field cuando hay shortname."""
        recorded = []

        async def call_ws(wsfunction, params):
            recorded.append((wsfunction, params))
            return []

        await adapter.get_courses("TEST101", call_ws)
        ws, params = recorded[0]
        assert ws == "core_course_get_courses_by_field"
        assert params["field"] == "shortname"
        assert params["value"] == "TEST101"

    def test_build_create_course_enrolment_params(self, adapter):
        """3.x: no agrega params de enrolment (no son parametros API estandar)."""
        params = {}
        course = {"enrolment_1": "self", "enrolment_1_role": "student"}
        adapter.build_create_course_enrolment_params(params, course, 0)
        assert params == {}  # no-op en Moodle 3.x real

    def test_build_create_course_enrolment_params_skips_when_missing(self, adapter):
        params = {}
        adapter.build_create_course_enrolment_params(params, {}, 0)
        assert params == {}


# ===========================================================================
# MoodleAdapterFactory
# ===========================================================================
class TestMoodleAdapterFactory:
    def test_exact_match_3_9(self):
        adapter = MoodleAdapterFactory.create("3.9")
        assert isinstance(adapter, Moodle3Adapter)

    def test_exact_match_3_8(self):
        adapter = MoodleAdapterFactory.create("3.8")
        assert isinstance(adapter, Moodle3Adapter)

    def test_unsupported_version_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            MoodleAdapterFactory.create("4.0")

    def test_unsupported_5x_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            MoodleAdapterFactory.create("5.2")
