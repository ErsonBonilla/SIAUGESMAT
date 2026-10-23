from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.errores_moodle import ErrorApiMoodle, ErrorMoodleSobrecargado
from app.services.mensajes_error import traducir_error
from app.workers.tareas_operaciones import (
    _asegurar_categoria_raiz,
    _entidad_existe,
    _formatear_error_moodle,
    procesar_lote_operacion,
)


def _make_moodle():
    m = MagicMock()
    m.cerrar = AsyncMock(return_value=None)
    return m


def _make_batch(
    id_lote="BATCH_001", tipo_entidad="courses", accion="delete", modalidad="DISTANCIA"
):
    batch = MagicMock()
    batch.id_lote = id_lote
    batch.tipo_entidad = tipo_entidad
    batch.accion = accion
    batch.modalidad = modalidad
    return batch


def _make_item(identificador="CURSE_001", **extra):
    item = MagicMock()
    item.id = 1
    item.identificador = identificador
    item.detalle = extra
    return item


class TestFormatMoodleError:
    def test_duplicate_user(self):
        e = MagicMock(codigo_error="duplicateuser", mensaje_espanol="")
        msg = _formatear_error_moodle(e, "users", _make_item())
        assert "ya existe" in msg

    def test_invalid_email(self):
        e = MagicMock(codigo_error="invalidemail", mensaje_espanol="")
        item = _make_item(email="bad-email")
        msg = _formatear_error_moodle(e, "users", item)
        assert "Email inv" in msg

    def test_duplicate_category(self):
        e = MagicMock(codigo_error="duplicatecategory", mensaje_espanol="")
        msg = _formatear_error_moodle(e, "categories", _make_item())
        assert "ya existe" in msg

    def test_cannot_find_parent(self):
        e = MagicMock(codigo_error="cannotfindparentcategory", mensaje_espanol="")
        msg = _formatear_error_moodle(e, "categories", _make_item())
        assert "no encontrada" in msg

    def test_fallback_to_spanish_message(self):
        e = MagicMock(codigo_error="unknown_code", mensaje_espanol="Error genérico")
        msg = _formatear_error_moodle(e, "courses", _make_item())
        assert msg == "Error genérico"


class TestProcessOperationBatch:
    def test_batch_not_found(self):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote", return_value=None),
        ):
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            db.close.assert_called_once()

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_courses(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item"),
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="courses", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item()
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_cursos = AsyncMock(return_value=[{"id": 1}])
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            moodle.eliminar_cursos.assert_called_once_with(["CURSE_001"])
            mock_complete.assert_called_once()
            assert mock_complete.call_args[0][1] == "BATCH_001"

    @pytest.mark.parametrize(
        ("estado_detencion", "paused_count", "cancelled_count"),
        [("paused", 1, 0), ("cancelled", 0, 1)],
    )
    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_lote_detenido_no_se_completa(
        self, mock_pending, mock_complete, estado_detencion, paused_count, cancelled_count
    ):
        """Un lote pausado o cancelado a mitad no debe marcarse como completado."""
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ),
            patch("app.workers.tareas_operaciones.actualizar_item"),
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="courses", accion="delete")
            mock_get_batch.return_value = batch
            mock_pending.return_value = [_make_item()]

            db = MagicMock()

            def _filter_by(**kwargs):
                m = MagicMock()
                estado = kwargs.get("estado")
                m.count.return_value = (
                    paused_count
                    if estado == "paused"
                    else (cancelled_count if estado == "cancelled" else 0)
                )
                return m

            db.query.return_value.filter_by.side_effect = _filter_by
            mock_sl.return_value = db

            procesar_lote_operacion("BATCH_001")

            mock_complete.assert_not_called()

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_course_not_found_idempotent(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item") as mock_update,
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="courses", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item()
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_cursos = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            mock_update.assert_any_call(
                db, 1, "completed", "Curso no encontrado en Moodle. Se omite (ya no existía)."
            )

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_user_transient_error_but_deleted(self, mock_pending, mock_complete):
        """Error transitorio al borrar pero la entidad ya no existe → completed."""
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item") as mock_update,
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="users", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_usuarios = AsyncMock(
                side_effect=ErrorMoodleSobrecargado("gateway time-out")
            )
            moodle.obtener_usuario_por_username = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            mock_update.assert_any_call(db, 1, "completed", None)

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_user_transient_error_still_exists(self, mock_pending, mock_complete):
        """Error transitorio y la entidad sigue existiendo → failed."""
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item") as mock_update,
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="users", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_usuarios = AsyncMock(
                side_effect=ErrorMoodleSobrecargado("gateway time-out")
            )
            moodle.obtener_usuario_por_username = AsyncMock(return_value={"id": 1})
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            exc = ErrorMoodleSobrecargado("gateway time-out")
            mock_update.assert_any_call(db, 1, "failed", traducir_error(exc))

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_user_not_found_idempotent(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item") as mock_update,
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="users", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_usuarios = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            mock_update.assert_any_call(
                db, 1, "completed", "Usuario no encontrado en Moodle. Se omite (ya no existía)."
            )

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_user_already_deleted_invaliduser(self, mock_pending, mock_complete):
        """Cuenta ya eliminada en Moodle (invaliduser en delete_users) → se omite."""
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item") as mock_update,
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="users", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_usuarios = AsyncMock(
                side_effect=ErrorApiMoodle("dml_missing_record_exception", "invaliduser")
            )
            moodle.obtener_usuario_por_username = AsyncMock(return_value={"id": 1})
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            mock_update.assert_any_call(
                db, 1, "completed", "Usuario no encontrado en Moodle. Se omite (ya no existía)."
            )

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_user_invaliduser_on_lookup_idempotent(self, mock_pending, mock_complete):
        """invaliduser también en el lookup de existencia → se omite, no falla."""
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item") as mock_update,
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="users", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_usuarios = AsyncMock(
                side_effect=ErrorApiMoodle("dml_missing_record_exception", "invaliduser")
            )
            moodle.obtener_usuario_por_username = AsyncMock(
                side_effect=ErrorApiMoodle("dml_missing_record_exception", "invaliduser")
            )
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            mock_update.assert_any_call(
                db, 1, "completed", "Usuario no encontrado en Moodle. Se omite (ya no existía)."
            )

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_categories(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item"),
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="categories", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item()
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.obtener_categorias = AsyncMock(return_value=[{"id": 5}])
            moodle.eliminar_categoria = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            procesar_lote_operacion("BATCH_001")
            moodle.eliminar_categoria.assert_called_once_with(5)

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_delete_users(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item"),
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="users", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item("user1")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_usuarios = AsyncMock(return_value=[{"id": 1}])
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            procesar_lote_operacion("BATCH_001")
            moodle.eliminar_usuarios.assert_called_once_with(["user1"])

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_create_users(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item"),
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="users", accion="create")
            mock_get_batch.return_value = batch
            item = _make_item("newuser", firstname="New", lastname="User", email="new@test.com")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.crear_usuarios = AsyncMock(return_value=[])
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            procesar_lote_operacion("BATCH_001")
            moodle.crear_usuarios.assert_called_once()

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_create_users_no_persiste_password(self, mock_pending, mock_complete):
        """La creación por CSV no envía contraseña: usa createpassword (Moodle genera)."""
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item"),
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="users", accion="create")
            mock_get_batch.return_value = batch
            item = _make_item("newuser", firstname="New", lastname="User", email="new@test.com")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.crear_usuarios = AsyncMock(return_value=[])
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            procesar_lote_operacion("BATCH_001")
            user_data = moodle.crear_usuarios.call_args[0][0][0]
            assert user_data["createpassword"] is True
            assert "password" not in user_data

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_create_categories(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item"),
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="categories", accion="create")
            mock_get_batch.return_value = batch
            item = _make_item("NEWCAT", idnumber="NEWCAT_01")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.crear_categorias = AsyncMock(return_value=[])
            moodle.obtener_categorias = AsyncMock(return_value=[{"id": 1}])
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            procesar_lote_operacion("BATCH_001")
            moodle.crear_categorias.assert_called_once()

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_visibility_show(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item"),
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="courses", accion="visibility")
            mock_get_batch.return_value = batch
            item = _make_item("CURSE_001", visibility="show")
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.obtener_cursos_por_campo = AsyncMock(return_value=[{"id": 10}])
            moodle.actualizar_cursos = AsyncMock(return_value=None)
            mock_get_ms.return_value = moodle
            mock_sl.return_value = MagicMock()
            procesar_lote_operacion("BATCH_001")
            moodle.actualizar_cursos.assert_called_once_with([{"id": 10, "visible": 1}])

    @patch("app.workers.tareas_operaciones.completar_lote")
    @patch("app.workers.tareas_operaciones.obtener_items_pendientes")
    def test_moodle_api_error_per_item(self, mock_pending, mock_complete):
        with (
            patch("app.workers.tareas_operaciones.SessionLocal") as mock_sl,
            patch("app.workers.tareas_operaciones.obtener_lote") as mock_get_batch,
            patch(
                "app.workers.tareas_operaciones.obtener_servicio_moodle",
                return_value=_make_moodle(),
            ) as mock_get_ms,
            patch("app.workers.tareas_operaciones.actualizar_item") as mock_update,
            patch("app.workers.tareas_operaciones.actualizar_conteos_lote", autospec=True),
        ):
            batch = _make_batch(tipo_entidad="courses", accion="delete")
            mock_get_batch.return_value = batch
            item = _make_item()
            mock_pending.return_value = [item]
            moodle = _make_moodle()
            moodle.eliminar_cursos = AsyncMock(
                side_effect=ErrorApiMoodle("API error", "unknownerror")
            )
            moodle.obtener_cursos = AsyncMock(return_value=[{"id": 1}])
            mock_get_ms.return_value = moodle
            db = MagicMock()
            mock_sl.return_value = db
            procesar_lote_operacion("BATCH_001")
            mock_update.assert_any_call(db, 1, "failed", "[unknownerror] API error")


class TestEntityExists:
    @pytest.mark.asyncio
    async def test_user_exists(self):
        moodle = _make_moodle()
        moodle.obtener_usuario_por_username = AsyncMock(return_value={"id": 5})
        assert await _entidad_existe(moodle, "users", "u1") is True

    @pytest.mark.asyncio
    async def test_user_missing(self):
        moodle = _make_moodle()
        moodle.obtener_usuario_por_username = AsyncMock(return_value=None)
        assert await _entidad_existe(moodle, "users", "u1") is False

    @pytest.mark.asyncio
    async def test_invaliduser_means_missing(self):
        moodle = _make_moodle()
        moodle.obtener_usuario_por_username = AsyncMock(
            side_effect=ErrorApiMoodle("dml_missing_record_exception", "invaliduser")
        )
        assert await _entidad_existe(moodle, "users", "u1") is False

    @pytest.mark.asyncio
    async def test_other_error_re_raises(self):
        moodle = _make_moodle()
        moodle.obtener_usuario_por_username = AsyncMock(
            side_effect=ErrorApiMoodle("API error", "unknownerror")
        )
        with pytest.raises(ErrorApiMoodle):
            await _entidad_existe(moodle, "users", "u1")


class TestEnsureRootCategory:
    @pytest.mark.asyncio
    async def test_already_exists(self):
        moodle = AsyncMock()
        moodle.obtener_categorias.return_value = [{"id": 1}]
        await _asegurar_categoria_raiz(moodle)
        moodle.crear_categorias.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_when_missing(self):
        moodle = AsyncMock()
        moodle.obtener_categorias.return_value = []
        await _asegurar_categoria_raiz(moodle)
        moodle.crear_categorias.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_on_error(self):
        moodle = AsyncMock()
        moodle.obtener_categorias.side_effect = ErrorApiMoodle("err", "unknownerror")
        with pytest.raises(ErrorApiMoodle):
            await _asegurar_categoria_raiz(moodle)
