"""
Pruebas unitarias de las mejoras M1-M4:

- M1.1: process_etl_item marca 'failed' tras agotar reintentos por sobrecarga.
- M1.3: marcador chord_active (set/clear) para el sweeper.
- M2.1: resolución de usuarios por username/cédula + detección de identidad.
- M2.2: create_user_if_not_exists recupera usuarios existentes por username.
- M3: spanish_message preserva el errorcode de Moodle.
- M4: recreate atómico (borrar + crear) propagado hasta create_course.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.integracion_moodle import IntegracionMoodle
from app.pipeline.comparacion_cursos.aplicar_accion import aplicar_accion
from app.pipeline.usuarios import nombres_difieren, normalizar_nombre
from app.services.errores_moodle import ErrorApiMoodle, ErrorMoodleSobrecargado
from app.services.operaciones_moodle import ServicioMoodle
from app.workers.phases.tarea_item import procesar_item_etl


@pytest.fixture
def moodle_integration():
    mock_service = AsyncMock(spec=ServicioMoodle)
    return IntegracionMoodle(mock_service)


def _make_item(item_id=1, accion="delete", execution_id=1, estado="processing", **extra):
    item = MagicMock()
    item.id = item_id
    item.estado = estado
    item.identificador = "IDENTIFIER_001"
    item.detalle = {
        "action": accion,
        "execution_id": execution_id,
        "modalidad": "DISTANCIA",
        **extra,
    }
    return item


def _make_moodle():
    m = MagicMock()
    m.cerrar = AsyncMock(return_value=None)
    return m

    # ---------------------------------------------------------------------------
    # M3: spanish_message preserva el errorcode
    # ---------------------------------------------------------------------------


class TestSpanishMessage:
    def test_prefixes_known_errorcode(self):
        err = ErrorApiMoodle("invalid", "invalidparameter")
        assert err.mensaje_espanol == "[invalidparameter] Parámetro inválido enviado a Moodle."

    def test_no_prefix_without_errorcode(self):
        err = ErrorApiMoodle("raw message", None)
        assert err.mensaje_espanol == "raw message"

    def test_prefixes_unknown_errorcode(self):
        err = ErrorApiMoodle("other", "weirdcode")
        assert err.mensaje_espanol == "[weirdcode] other"

        # ---------------------------------------------------------------------------
        # M2.1: normalización y detección de diferencias de identidad
        # ---------------------------------------------------------------------------


class TestNameComparison:
    def test_normalize_removes_accents_and_case(self):
        assert normalizar_nombre("  MARÍA  José  ") == "maria jose"

    def test_same_name_not_different(self):
        assert nombres_difieren("María José Suárez", "MARIA JOSE SUAREZ") is False

    def test_different_name_is_different(self):
        assert nombres_difieren("María José Suárez", "Carlos Andrés López") is True

    def test_minor_token_overlap_not_different(self):
        # Comparten >50% de tokens (apellidos coinciden)
        assert nombres_difieren("Ana María Pérez", "Ana Pérez") is False

    def test_empty_names_not_different(self):
        assert nombres_difieren("", "") is False

        # ---------------------------------------------------------------------------
        # M2.2: create_user_if_not_exists recupera por username
        # ---------------------------------------------------------------------------


class TestCreateUserIfNotExistsRecovery:
    @pytest.mark.asyncio
    async def test_existing_user_by_username_returns_not_created(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_usuarios.return_value = []  # no encontrado por email
        integ.servicio.obtener_usuario_por_username.return_value = {
            "username": "teacher1",
            "id": 9,
        }
        username, created = await integ.crear_usuario_si_no_existe(
            {
                "email": "teacher1@ut.edu.co",
                "firstname": "Ana",
                "lastname": "Pérez",
            }
        )
        assert username == "teacher1"
        assert created is False
        integ.servicio.crear_usuarios.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_username_lookup_error_returns_none(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_usuarios.return_value = []
        integ.servicio.obtener_usuario_por_username.side_effect = ErrorApiMoodle("boom")
        username, created = await integ.crear_usuario_si_no_existe(
            {
                "email": "teacher1@ut.edu.co",
            }
        )
        assert username is None
        assert created is False

        # ---------------------------------------------------------------------------
        # M4: create_course con recreate atómico
        # ---------------------------------------------------------------------------


class TestCreateCourseRecreate:
    @pytest.mark.asyncio
    async def test_recreate_deletes_then_creates(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.side_effect = [
            [{"shortname": "EXISTING", "id": "1"}],  # existe → borrar
            [],  # verificación: ya no existe
            [{"shortname": "EXISTING", "id": "2"}],  # creado
        ]
        integ.servicio.eliminar_cursos.return_value = {"status": "ok"}
        integ.servicio.crear_cursos.return_value = [{"shortname": "EXISTING", "id": "2"}]
        result = await integ.crear_curso(
            "EXISTING",
            "Existing",
            "CAT-01",
            recreate=True,
        )
        assert result is True
        integ.servicio.eliminar_cursos.assert_awaited_once_with(["EXISTING"])

    @pytest.mark.asyncio
    async def test_recreate_returns_false_if_course_persists(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.return_value = [{"shortname": "EXISTING", "id": "1"}]
        integ.servicio.eliminar_cursos.return_value = None  # no borra
        result = await integ.crear_curso(
            "EXISTING",
            "Existing",
            "CAT-01",
            recreate=True,
        )
        assert result is False
        assert "persiste" in integ.ultimo_error

    @pytest.mark.asyncio
    async def test_no_recreate_skips_existing(self, moodle_integration):
        integ = moodle_integration
        integ.servicio.obtener_cursos.return_value = [{"shortname": "EXISTING", "id": "1"}]
        result = await integ.crear_curso("EXISTING", "Existing", "CAT-01")
        assert result is True
        integ.servicio.eliminar_cursos.assert_not_awaited()

        # ---------------------------------------------------------------------------
        # M4: apply_action propaga "recreate": True a to_create
        # ---------------------------------------------------------------------------


class TestApplyActionRecreate:
    def test_recreate_adds_flag_to_create(self):
        to_create, to_delete = [], []
        aplicar_accion(
            "recreate",
            {"old_shortname": "OLD-1", "reason": "contenido renovado"},
            "NEW-1",
            "prof",
            None,
            to_create,
            to_delete,
            [],
            [],
            [],
            [],
            [],
        )
        assert to_delete == [
            {
                "shortname": "OLD-1",
                "old_shortname": "OLD-1",
                "reason": "contenido renovado",
            }
        ]
        assert to_create == [
            {
                "shortname": "NEW-1",
                "professor": "prof",
                "recreate": True,
                "reason": "contenido renovado",
                "old_shortname": "OLD-1",
            }
        ]

    def test_plain_create_has_no_recreate_flag(self):
        to_create, to_delete = [], []
        aplicar_accion(
            "create",
            {},
            "NEW-1",
            "prof",
            None,
            to_create,
            to_delete,
            [],
            [],
            [],
            [],
            [],
        )
        assert to_create == [{"shortname": "NEW-1", "professor": "prof"}]

        # ---------------------------------------------------------------------------
        # M4: item_task pasa recreate desde el detail del item
        # ---------------------------------------------------------------------------


class TestItemTaskRecreate:
    def test_create_course_receives_recreate_flag(self):
        item = MagicMock()
        item.id = 1
        item.estado = "pending"
        item.identificador = "IDENTIFIER_001"
        item.detalle = {
            "action": "create",
            "execution_id": 1,
            "modalidad": "DISTANCIA",
            "fullname": "New Course",
            "category_idnumber": "CAT_01",
            "template_id": None,
            "recreate": True,
        }
        moodle = MagicMock()
        moodle.cerrar = AsyncMock(return_value=None)
        mock_integ = AsyncMock()
        mock_integ.crear_curso.return_value = True
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item", return_value=item),
            patch("app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=moodle),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item"),
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ_cls.return_value = mock_integ
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)
        mock_integ.crear_curso.assert_called_once_with(
            shortname="IDENTIFIER_001",
            fullname="New Course",
            category_idnumber="CAT_01",
            template_id=None,
            recreate=True,
        )

        # ---------------------------------------------------------------------------
        # M1.1: item agota reintentos por sobrecarga → marcado failed (no rompe chord)
        # ---------------------------------------------------------------------------


class TestItemTaskOverloadExhaustion:
    def test_overloaded_exhausts_retries_marks_failed(self):
        moodle = _make_moodle()
        mock_integ = AsyncMock()
        mock_integ.eliminar_curso.side_effect = ErrorMoodleSobrecargado("504 gateway time-out")
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch(
                "app.workers.phases.tarea_item.obtener_item",
                return_value=_make_item(accion="delete"),
            ),
            patch("app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=moodle),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.debe_cancelarse", return_value=False),
            patch("app.workers.phases.tarea_item.actualizar_item") as mock_update,
            patch("app.workers.phases.tarea_item._manejar_error"),
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
            patch.object(procesar_item_etl, "max_retries", 0),
        ):
            mock_integ_cls.return_value = mock_integ
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)  # no debe lanzar: el chord no debe romperse
        mock_update.assert_any_call(
            mock_sl.return_value,
            1,
            "failed",
            "Agotados reintentos por sobrecarga de Moodle",
        )

    def test_overloaded_before_max_retries_raises(self):
        moodle = _make_moodle()
        mock_integ = AsyncMock()
        mock_integ.eliminar_curso.side_effect = ErrorMoodleSobrecargado("504 gateway time-out")
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch(
                "app.workers.phases.tarea_item.obtener_item",
                return_value=_make_item(accion="delete"),
            ),
            patch("app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=moodle),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.debe_cancelarse", return_value=False),
            patch("app.workers.phases.tarea_item.actualizar_item") as mock_update,
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
            patch.object(procesar_item_etl, "max_retries", 3),
        ):
            mock_integ_cls.return_value = mock_integ
            mock_sl.return_value = MagicMock()
            with pytest.raises(ErrorMoodleSobrecargado):
                procesar_item_etl(1)  # aún hay reintentos: se relanza para retry de Celery
        for call in mock_update.call_args_list:
            assert "Agotados reintentos" not in str(call)

            # ---------------------------------------------------------------------------
            # M1.3: marcador chord_active para el sweeper
            # ---------------------------------------------------------------------------


class TestChordActiveMarker:
    def test_set_and_clear(self, test_db):
        from app.db.modelos import Ejecucion
        from app.repositories.repositorio_ejecuciones import (
            limpiar_chord_activo,
            marcar_chord_activo,
        )

        ex = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025A",
            estado="running",
            modalidad="DISTANCIA",
            creado_en=datetime.now(UTC),
        )
        test_db.add(ex)
        test_db.commit()
        test_db.refresh(ex)

        marcar_chord_activo(test_db, ex.id, minutes=120)
        test_db.refresh(ex)
        active_ts = ex.checkpoint_fase.get("chord_active")
        assert isinstance(active_ts, str)
        future = datetime.fromisoformat(active_ts)
        assert future > datetime.now(UTC)

        limpiar_chord_activo(test_db, ex.id)
        test_db.refresh(ex)
        assert ex.checkpoint_fase.get("chord_active") is None

    def test_chord_active_default_uses_settings(self, test_db):
        from app.core.config import settings
        from app.db.modelos import Ejecucion
        from app.repositories.repositorio_ejecuciones import marcar_chord_activo

        ex = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025A",
            estado="running",
            modalidad="DISTANCIA",
            creado_en=datetime.now(UTC),
        )
        test_db.add(ex)
        test_db.commit()
        test_db.refresh(ex)

        marcar_chord_activo(test_db, ex.id)
        test_db.refresh(ex)
        ts = datetime.fromisoformat(ex.checkpoint_fase["chord_active"])
        expected = datetime.now(UTC) + timedelta(minutes=settings.CHORD_ACTIVE_MINUTES)
        assert abs((ts - expected).total_seconds()) < 5

        # ---------------------------------------------------------------------------
        # M1.4: sweeper recover_stuck_phase relanza fases con chord huérfano
        # ---------------------------------------------------------------------------


class TestRecoverStuckPhase:
    def _make_execution(self, test_db, estado="running", checkpoint=None):
        from app.db.modelos import Ejecucion

        ex = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025A",
            estado=estado,
            modalidad="DISTANCIA",
            creado_en=datetime.now(UTC),
            checkpoint_fase=checkpoint or {},
        )
        test_db.add(ex)
        test_db.commit()
        test_db.refresh(ex)
        return ex

    def test_relaunches_phase3_when_chord_expired(self, test_db):
        ex = self._make_execution(test_db)
        with (
            patch(
                "app.workers.phases.comunes._obtener_items_pendientes", return_value=[MagicMock()]
            ),
            patch("app.workers.utilidades.reiniciar_items_atascados", return_value=[]),
            patch("app.workers.phases.fase3_estructura.al_terminar_items_eliminacion") as mock_cb,
        ):
            from app.workers.tareas_limpieza import recuperar_fase_atascada

            recuperar_fase_atascada()
        mock_cb.delay.assert_called_once_with([], ex.id)

    def test_relaunches_phase4(self, test_db):
        ex = self._make_execution(test_db)
        with (
            patch(
                "app.workers.phases.comunes._obtener_items_pendientes",
                side_effect=[[], [MagicMock()]],
            ),
            patch("app.workers.utilidades.reiniciar_items_atascados", return_value=[]),
            patch("app.workers.tareas_limpieza._relanzar_fase4") as mock_relaunch,
        ):
            from app.workers.tareas_limpieza import recuperar_fase_atascada

            recuperar_fase_atascada()
        mock_relaunch.assert_called_once()
        assert mock_relaunch.call_args.args[1] == ex.id

    def test_skips_relaunch_when_chord_active(self, test_db):
        future = (datetime.now(UTC) + timedelta(minutes=30)).isoformat()
        self._make_execution(test_db, checkpoint={"chord_active": future})
        with (
            patch(
                "app.workers.phases.comunes._obtener_items_pendientes", return_value=[MagicMock()]
            ) as mock_get,
            patch("app.workers.utilidades.reiniciar_items_atascados", return_value=[]),
            patch("app.workers.phases.fase3_estructura.al_terminar_items_eliminacion") as mock_cb,
        ):
            from app.workers.tareas_limpieza import recuperar_fase_atascada

            recuperar_fase_atascada()
        mock_get.assert_called()
        mock_cb.delay.assert_not_called()

    def test_phase4_relaunch_refreshes_chord_active(self, test_db):
        from app.workers.phases.comunes import al_terminar_items_fase

        ex = self._make_execution(test_db)
        with (
            patch(
                "app.workers.phases.comunes._obtener_items_pendientes", return_value=[MagicMock()]
            ),
            patch("app.workers.phases.comunes.reiniciar_items_atascados", return_value=[]),
            patch("app.workers.phases.comunes.procesar_item_etl") as mock_task,
            patch("app.workers.phases.comunes.chord") as mock_chord,
            patch("app.workers.phases.comunes._marcar_chord_activo") as mock_mark,
        ):
            mock_task.si.return_value = "sig1"
            mock_chord.return_value = MagicMock()
            al_terminar_items_fase([], ex.id, "4")
        mock_mark.assert_called_once_with(ex.id)
        mock_chord.assert_called_once()

    def test_relaunches_phase12_when_stale_and_no_items(self, test_db):
        old = datetime.now(UTC) - timedelta(minutes=40)
        ex = self._make_execution(test_db, checkpoint={"_retry_count": 0})
        ex.progreso_actualizado_en = old
        ex.creado_en = old
        test_db.commit()
        with (
            patch("app.workers.phases.comunes._obtener_items_pendientes", side_effect=[[], []]),
            patch("app.workers.phases.comunes._existen_items_para_ejecucion", return_value=False),
            patch("app.workers.tareas.procesar_archivo_etl") as mock_file,
            patch("os.path.isfile", return_value=True),
        ):
            from app.workers.tareas_limpieza import recuperar_fase_atascada

            recuperar_fase_atascada()
        mock_file.delay.assert_called_once()
        args = mock_file.delay.call_args[0]
        assert args[0] == ex.id

    def test_skips_relaunch_phase12_when_heartbeat_recent(self, test_db):
        fresh = datetime.now(UTC) - timedelta(minutes=5)
        ex = self._make_execution(test_db, checkpoint={"_retry_count": 0})
        ex.progreso_actualizado_en = fresh
        ex.creado_en = fresh
        test_db.commit()
        with (
            patch("app.workers.phases.comunes._obtener_items_pendientes", side_effect=[[], []]),
            patch("app.workers.phases.comunes._existen_items_para_ejecucion", return_value=False),
            patch("app.workers.tareas.procesar_archivo_etl") as mock_file,
        ):
            from app.workers.tareas_limpieza import recuperar_fase_atascada

            recuperar_fase_atascada()
        mock_file.delay.assert_not_called()

    def test_skips_relaunch_phase12_when_retry_exceeded(self, test_db):
        old = datetime.now(UTC) - timedelta(minutes=40)
        ex = self._make_execution(test_db, checkpoint={"_retry_count": 3})
        ex.progreso_actualizado_en = old
        ex.creado_en = old
        test_db.commit()
        with (
            patch("app.workers.phases.comunes._obtener_items_pendientes", side_effect=[[], []]),
            patch("app.workers.phases.comunes._existen_items_para_ejecucion", return_value=False),
            patch("app.workers.tareas.procesar_archivo_etl") as mock_file,
            patch("os.path.isfile", return_value=True),
        ):
            from app.workers.tareas_limpieza import recuperar_fase_atascada

            recuperar_fase_atascada()
        mock_file.delay.assert_not_called()

        # ---------------------------------------------------------------------------
        # enrol_failed — normalización de motivos de fallo de matrícula
        # ---------------------------------------------------------------------------


class TestNormalizeEnrolReason:
    def test_user_not_found_spanish(self):
        from app.workers.phases.tarea_item import _normalizar_motivo_matriculacion

        assert (
            _normalizar_motivo_matriculacion("Usuario no encontrado en Moodle: u1")
            == "user_not_found"
        )

    def test_user_inactive_by_code(self):
        from app.workers.phases.tarea_item import _normalizar_motivo_matriculacion

        assert _normalizar_motivo_matriculacion("usernotactive: user suspended") == "user_inactive"

    def test_course_not_found(self):
        from app.workers.phases.tarea_item import _normalizar_motivo_matriculacion

        assert (
            _normalizar_motivo_matriculacion("Curso no encontrado en Moodle: C1")
            == "course_not_found"
        )

    def test_fallback_raw(self):
        from app.workers.phases.tarea_item import _normalizar_motivo_matriculacion

        assert _normalizar_motivo_matriculacion("unknown weird error") == "unknown weird error"

        # ---------------------------------------------------------------------------
        # CAS: claim_item atómico
        # ---------------------------------------------------------------------------


class TestClaimItem:
    def test_claims_from_pending(self, test_db):
        from app.db.modelos import ItemOperacion, LoteOperacion
        from app.repositories.repositorio_operaciones import reclamar_item

        batch = LoteOperacion(
            id_lote="etl_test_claim",
            tipo_entidad="test",
            accion="test",
            total=1,
            modalidad="DISTANCIA",
        )
        test_db.add(batch)
        test_db.flush()
        item = ItemOperacion(
            id_lote="etl_test_claim",
            identificador="ID1",
            detalle={"action": "test"},
            estado="pending",
        )
        test_db.add(item)
        test_db.flush()
        item_id = item.id
        assert reclamar_item(test_db, item_id) is True
        test_db.refresh(item)
        assert item.estado == "processing"

    def test_second_claim_fails(self, test_db):
        from app.db.modelos import ItemOperacion, LoteOperacion
        from app.repositories.repositorio_operaciones import reclamar_item

        batch = LoteOperacion(
            id_lote="etl_test_claim2",
            tipo_entidad="test",
            accion="test",
            total=1,
            modalidad="DISTANCIA",
        )
        test_db.add(batch)
        test_db.flush()
        item = ItemOperacion(
            id_lote="etl_test_claim2",
            identificador="ID1",
            detalle={"action": "test"},
            estado="pending",
        )
        test_db.add(item)
        test_db.flush()
        item_id = item.id
        assert reclamar_item(test_db, item_id) is True
        assert reclamar_item(test_db, item_id) is False

        # ---------------------------------------------------------------------------
        # Chord ordering: set_chord_active antes de lanzar
        # ---------------------------------------------------------------------------


class TestChordActiveOrdering:
    def test_launch_items_chord_marks_before_chord(self):
        from app.workers.phases.comunes import _lanzar_chord_items

        item = MagicMock()
        item.id = 1
        calls = []
        with (
            patch("app.workers.phases.comunes.chord") as mock_chord_fn,
            patch("app.workers.phases.comunes._marcar_chord_activo") as mock_mark,
        ):
            mock_mark.side_effect = lambda *a, **kw: calls.append("mark")
            mock_chord_fn.side_effect = lambda *a, **kw: calls.append("chord") or MagicMock()
            _lanzar_chord_items(1, [item])
        assert calls == ["mark", "chord"]

    def test_launch_delete_chord_marks_before_chord(self):
        from app.workers.phases.fase3_estructura import _lanzar_chord_eliminacion

        item = MagicMock()
        item.id = 1
        calls = []
        with (
            patch("app.workers.phases.fase3_estructura.chord") as mock_chord_fn,
            patch(
                "app.workers.phases.fase3_estructura._marcar_chord_eliminacion_activo"
            ) as mock_mark,
        ):
            mock_mark.side_effect = lambda *a, **kw: calls.append("mark")
            mock_chord_fn.side_effect = lambda *a, **kw: calls.append("chord") or MagicMock()
            _lanzar_chord_eliminacion(1, [item])
        assert calls == ["mark", "chord"]

        # ---------------------------------------------------------------------------
        # M2.5: reset de items 'failed' reintentables con tope de intentos
        # ---------------------------------------------------------------------------


class TestResetFailedItems:
    def test_resets_failed_below_attempt_cap(self, test_db):
        from app.db.modelos import Ejecucion, ItemOperacion
        from app.workers.phases.comunes import _reiniciar_items_fallidos

        ex = Ejecucion(
            nombre_archivo="test.xlsx", semestre="2025A", estado="running", modalidad="DISTANCIA"
        )
        test_db.add(ex)
        test_db.commit()

        retryable = ItemOperacion(
            id_lote=f"etl_3_activate_{ex.id}",
            identificador="A",
            estado="failed",
            intento=1,
            detalle={"action": "activate"},
        )
        exhausted = ItemOperacion(
            id_lote=f"etl_3_activate_{ex.id}",
            identificador="B",
            estado="failed",
            intento=3,
            detalle={"action": "activate"},
        )
        test_db.add_all([retryable, exhausted])
        test_db.commit()

        _reiniciar_items_fallidos(test_db, ex.id, "3")

        test_db.refresh(retryable)
        test_db.refresh(exhausted)
        assert retryable.estado == "pending"
        assert exhausted.estado == "failed"

        # ---------------------------------------------------------------------------
        # M3.2: sweeper resetea items individuales atascados pese a actividad reciente
        # ---------------------------------------------------------------------------


class TestSweeperResetsStaleItems:
    def _stale_item(self, test_db, eid, batch, identifier, minutes_ago):
        from app.db.modelos import ItemOperacion

        item = ItemOperacion(
            id_lote=batch,
            identificador=identifier,
            estado="processing",
            detalle={"action": "create"},
            actualizado_en=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )
        test_db.add(item)
        return item

    def test_resets_stale_item_even_with_recent_activity(self, test_db):
        from app.db.modelos import Ejecucion
        from app.workers.tareas_limpieza import recuperar_fase_atascada

        ex = Ejecucion(
            nombre_archivo="test.xlsx", semestre="2025A", estado="running", modalidad="DISTANCIA"
        )
        test_db.add(ex)
        test_db.commit()

        stale = self._stale_item(test_db, ex.id, f"etl_3_hide_{ex.id}", "stale-1", minutes_ago=60)
        recent = self._stale_item(
            test_db, ex.id, f"etl_3_create_{ex.id}", "recent-1", minutes_ago=1
        )
        test_db.commit()

        with patch("app.workers.phases.comunes._obtener_items_pendientes", return_value=[]):
            recuperar_fase_atascada()

        test_db.refresh(stale)
        test_db.refresh(recent)
        assert stale.estado == "pending"
        assert recent.estado == "processing"

        # ---------------------------------------------------------------------------
        # M3.3: limpieza de items huérfanos de ejecuciones finalizadas
        # ---------------------------------------------------------------------------


class TestResolveOrphanItems:
    def _make_execution(self, test_db, estado="running"):
        from app.db.modelos import Ejecucion

        ex = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025A",
            estado=estado,
            modalidad="DISTANCIA",
            creado_en=datetime.now(UTC),
        )
        test_db.add(ex)
        test_db.commit()
        test_db.refresh(ex)
        return ex

    def _agregar_items(self, test_db, eid, batch, statuses):
        from app.repositories.repositorio_operaciones import agregar_item

        items = []
        for i, status in enumerate(statuses):
            item = agregar_item(
                test_db,
                batch,
                f"id-{i}",
                detalle={"action": "create", "execution_id": eid},
                estado=status,
            )
            items.append(item)
        test_db.commit()
        for item in items:
            test_db.refresh(item)
        return items

    def test_marks_orphans_of_completed_execution_as_failed(self, test_db):
        from app.repositories.repositorio_operaciones import (
            obtener_lote_activo,
            resolver_items_huerfanos,
        )

        ex = self._make_execution(test_db, estado="completed")
        batch = f"etl_3_create_{ex.id}"
        from app.repositories.repositorio_operaciones import crear_lote

        crear_lote(test_db, batch, "courses", "create", 2, "DISTANCIA")
        pending, processing = self._agregar_items(test_db, ex.id, batch, ["pending", "processing"])
        test_db.commit()

        resolved = resolver_items_huerfanos(test_db)

        assert len(resolved) == 2
        test_db.refresh(pending)
        test_db.refresh(processing)
        assert pending.estado == "failed"
        assert processing.estado == "failed"
        assert pending.mensaje_error == "Ejecución finalizada, item huérfano"
        assert obtener_lote_activo(test_db, "DISTANCIA") is None

    def test_keeps_items_of_running_execution(self, test_db):
        from app.repositories.repositorio_operaciones import (
            obtener_lote_activo,
            resolver_items_huerfanos,
        )

        ex = self._make_execution(test_db, estado="running")
        batch = f"etl_3_create_{ex.id}"
        from app.repositories.repositorio_operaciones import crear_lote

        crear_lote(test_db, batch, "courses", "create", 1, "DISTANCIA")
        (item,) = self._agregar_items(test_db, ex.id, batch, ["pending"])

        resolved = resolver_items_huerfanos(test_db)

        assert resolved == []
        test_db.refresh(item)
        assert item.estado == "pending"
        assert obtener_lote_activo(test_db, "DISTANCIA") is not None

    def test_ignores_items_without_execution_id(self, test_db):
        from app.repositories.repositorio_operaciones import (
            agregar_item,
            crear_lote,
            resolver_items_huerfanos,
        )

        crear_lote(test_db, "csv-batch-1", "courses", "visibility", 1, "DISTANCIA")
        item = agregar_item(
            test_db, "csv-batch-1", "CSV1", detalle={"visibility": "show"}, estado="pending"
        )
        test_db.commit()
        test_db.refresh(item)

        resolved = resolver_items_huerfanos(test_db)

        assert resolved == []
        test_db.refresh(item)
        assert item.estado == "pending"

        # ---------------------------------------------------------------------------
        # M4.1: sync de contadores de lote ETL desde operation_items
        # ---------------------------------------------------------------------------


class TestSyncBatchCounts:
    def test_updates_batch_totals_from_items(self, test_db):
        from app.db.modelos import Ejecucion
        from app.repositories.repositorio_operaciones import agregar_item, crear_lote
        from app.workers.phases.comunes import _sincronizar_conteos_lote

        ex = Ejecucion(
            nombre_archivo="test.xlsx", semestre="2025A", estado="running", modalidad="DISTANCIA"
        )
        test_db.add(ex)
        test_db.commit()

        batch_id = f"etl_3_activate_{ex.id}"
        batch = crear_lote(test_db, batch_id, "courses", "activate", 3, "DISTANCIA")
        agregar_item(test_db, batch_id, "A", {"action": "activate"}, estado="completed")
        agregar_item(test_db, batch_id, "B", {"action": "activate"}, estado="completed")
        agregar_item(test_db, batch_id, "C", {"action": "activate"}, estado="failed")
        test_db.commit()

        _sincronizar_conteos_lote(test_db, ex.id)

        test_db.refresh(batch)
        assert batch.completados == 2
        assert batch.fallidos == 1
