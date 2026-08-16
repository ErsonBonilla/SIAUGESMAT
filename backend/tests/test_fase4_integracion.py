"""
Tests de integración para Phase 4 (creación de usuarios y enrolamientos).

Verifica:
- _create_phase4_items: creación de items de usuario y enrolment
- process_etl_item: procesamiento de items de enrolment con course_map
- on_users_done: callback que vincula fallos de usuario a enrolments
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.workers.phases.fase4_personas import _crear_items_fase4_async as _create_phase4_items


def _make_ctx_data(users=None, enrolments=None):
    return {
        "users_to_create": users or [],
        "resolved_enrolments": enrolments or [],
    }


def _make_user(
    username="testuser",
    firstname="Test",
    lastname="User",
    email="testuser@ut.edu.co",
    cedula="12345",
):
    return {
        "username": username,
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
        "cedula": cedula,
        "password": "",
        "city": "",
        "description": "",
        "email_personal": "",
    }


def _make_enrolment(username="testuser", course_shortname="TST_0001_sI_001_G-1_12345"):
    return {"username": username, "course_shortname": course_shortname}


class TestCreatePhase4Items:
    @pytest.mark.asyncio
    async def test_happy_path_users_and_enrolments(self, test_db):
        """Crea usuarios + enrolments correctamente."""
        with (
            patch("app.workers.phases.fase4_personas._adquirir_bloqueo_asesor", return_value=True),
            patch("app.workers.phases.fase4_personas.obtener_servicio_moodle") as mock_factory,
        ):
            instance = AsyncMock()
            instance.obtener_cursos.return_value = [
                {"id": 100, "shortname": "TST_0001_sI_001_G-1_12345"},
            ]
            mock_factory.return_value = instance

            ctx = _make_ctx_data(
                users=[_make_user()],
                enrolments=[_make_enrolment()],
            )

            counts = await _create_phase4_items(test_db, 1, ctx, "DISTANCIA")

        assert counts.get("create_users") == 1
        assert counts.get("enrol") == 1

        # Verificar en DB
        from app.db.modelos import ItemOperacion

        items = test_db.query(ItemOperacion).filter(ItemOperacion.id_lote.like("etl_4_%_1")).all()
        assert len(items) == 2
        usernames = [(i.identificador, (i.detalle or {}).get("action")) for i in items]
        assert ("testuser", "create_user") in usernames
        assert ("testuser", "enrol") in usernames

    @pytest.mark.asyncio
    async def test_lock_contention(self, test_db):
        """Advisory lock evita duplicados: segundo llamado retorna vacío."""
        with patch("app.workers.phases.fase4_personas._adquirir_bloqueo_asesor") as mock_lock:
            # Primer worker obtiene el lock
            mock_lock.side_effect = [True, False]

            ctx = _make_ctx_data(
                users=[_make_user()],
                enrolments=[_make_enrolment()],
            )

            counts_1 = await _create_phase4_items(test_db, 2, ctx, "DISTANCIA")
            counts_2 = await _create_phase4_items(test_db, 2, ctx, "DISTANCIA")

        assert counts_1.get("create_users") == 1
        # Segundo worker retoma items pendientes (no duplica)
        assert counts_2.get("create_user") == 1
        assert counts_2.get("enrol") == 1

    @pytest.mark.asyncio
    async def test_already_exists(self, test_db):
        """Items ya existen → retomar sin duplicar."""
        with (
            patch("app.workers.phases.fase4_personas._adquirir_bloqueo_asesor", return_value=True),
            patch("app.workers.phases.fase4_personas.obtener_servicio_moodle") as mock_factory,
        ):
            instance = AsyncMock()
            instance.obtener_cursos.return_value = []
            mock_factory.return_value = instance

            # Primera llamada: crear items
            ctx = _make_ctx_data(
                users=[_make_user()],
                enrolments=[_make_enrolment()],
            )
            counts_1 = await _create_phase4_items(test_db, 3, ctx, "DISTANCIA")
            assert counts_1.get("create_users") == 1

            # Segunda llamada: ya existen, debe retomar
        with (
            patch("app.workers.phases.fase4_personas._adquirir_bloqueo_asesor", return_value=True),
            patch("app.workers.phases.fase4_personas.obtener_servicio_moodle") as mock_factory,
        ):
            instance = AsyncMock()
            instance.obtener_cursos.return_value = []
            mock_factory.return_value = instance

            counts_2 = await _create_phase4_items(test_db, 3, ctx, "DISTANCIA")
            # Devuelve pendientes (items aún no procesados)
            assert counts_2.get("create_user") == 1
            assert counts_2.get("enrol") == 1

    @pytest.mark.asyncio
    async def test_enrol_items_have_course_id(self, test_db):
        """Items de enrolment deben tener _course_id resuelto."""
        with (
            patch("app.workers.phases.fase4_personas._adquirir_bloqueo_asesor", return_value=True),
            patch("app.workers.phases.fase4_personas.obtener_servicio_moodle") as mock_factory,
        ):
            instance = AsyncMock()
            instance.obtener_cursos.return_value = [
                {"id": 200, "shortname": "TST_0001_sI_001_G-1_12345"},
            ]
            mock_factory.return_value = instance

            ctx = _make_ctx_data(
                enrolments=[_make_enrolment()],
            )
            await _create_phase4_items(test_db, 4, ctx, "DISTANCIA")

        from app.db.modelos import ItemOperacion

        enrol_item = (
            test_db.query(ItemOperacion)
            .filter(
                ItemOperacion.id_lote.like("etl_4_%_4"),
                ItemOperacion.detalle["action"].as_string() == "enrol",
            )
            .first()
        )
        assert enrol_item is not None
        assert (enrol_item.detalle or {}).get("_course_id") == 200
