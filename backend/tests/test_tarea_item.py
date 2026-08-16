import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.errores_moodle import ErrorMoodleSobrecargado
from app.workers.phases.tarea_item import procesar_item_etl


def _make_item(item_id=1, accion="delete", execution_id=1, estado="pending", **extra):
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


class TestProcessEtlItem:
    def test_item_not_found(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item", return_value=None),
        ):
            mock_db = MagicMock()
            mock_sl.return_value = mock_db
            procesar_item_etl(1)
            mock_db.close.assert_called_once()

    def test_item_already_completed(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
        ):
            mock_get.return_value = _make_item(estado="completed")
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)

    def test_missing_action(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch("app.workers.phases.tarea_item.actualizar_item") as mock_update,
        ):
            item = _make_item()
            item.detalle = {}
            mock_get.return_value = item
            db = MagicMock()
            mock_sl.return_value = db
            procesar_item_etl(1)
            mock_update.assert_called_once_with(db, item.id, "failed", "Falta 'action' en detail")

    def test_cancelled_execution(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch("app.workers.phases.tarea_item.debe_cancelarse", return_value=True),
            patch("app.workers.phases.tarea_item.actualizar_item") as mock_update,
        ):
            mock_get.return_value = _make_item()
            db = MagicMock()
            mock_sl.return_value = db
            procesar_item_etl(1)
            mock_update.assert_called_once_with(db, 1, "failed", "Ejecución cancelada")

    def test_unknown_action(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle"),
            patch("app.workers.phases.tarea_item.actualizar_item") as mock_update,
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_get.return_value = _make_item(accion="invalid")
            db = MagicMock()
            mock_sl.return_value = db
            procesar_item_etl(1)
            mock_update.assert_any_call(db, 1, "failed", "Acción desconocida: invalid")

    @pytest.mark.parametrize(
        "action,method",
        [
            ("delete", "eliminar_curso"),
            ("activate", "activar_curso"),
            ("hide", "ocultar_curso"),
        ],
    )
    def test_simple_actions_success(self, action, method):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item"),
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            getattr(mock_integ, method).return_value = True
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item(accion=action)
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)

    @pytest.mark.parametrize(
        "action,method",
        [
            ("delete", "eliminar_curso"),
            ("activate", "activar_curso"),
            ("hide", "ocultar_curso"),
        ],
    )
    def test_simple_actions_failure(self, action, method):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item") as mock_update,
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            getattr(mock_integ, method).return_value = False
            mock_integ.ultimo_error = f"Error in {method}"
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item(accion=action)
            db = MagicMock()
            mock_sl.return_value = db
            procesar_item_etl(1)
            mock_update.assert_any_call(db, 1, "failed", f"Error in {method}")

    def test_rename_success(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item"),
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.renombrar_curso.return_value = True
            mock_integ_cls.return_value = mock_integ
            item = _make_item(accion="rename", old_shortname="OLD_001", fullname="New Fullname")
            mock_get.return_value = item
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)
            mock_integ.renombrar_curso.assert_called_once_with(
                old_shortname="OLD_001", new_shortname="IDENTIFIER_001", new_fullname="New Fullname"
            )

    def test_create_course_success(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item"),
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.crear_curso.return_value = True
            mock_integ_cls.return_value = mock_integ
            item = _make_item(
                accion="create", fullname="New Course", category_idnumber="CAT_01", template_id=42
            )
            mock_get.return_value = item
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)
            mock_integ.crear_curso.assert_called_once_with(
                shortname="IDENTIFIER_001",
                fullname="New Course",
                category_idnumber="CAT_01",
                template_id=42,
                recreate=False,
            )

    def test_create_user_success(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item"),
            patch("app.workers.phases.tarea_item.guardar_log") as mock_save_log,
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.crear_usuario_si_no_existe.return_value = ("newuser", True)
            mock_integ_cls.return_value = mock_integ
            item = _make_item(
                accion="create_user",
                firstname="John",
                lastname="Doe",
                email="john@test.com",
                password="pwd123",
                cedula="123",
                city="City",
                description="desc",
            )
            mock_get.return_value = item
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)
            mock_save_log.assert_called_once()
            _, _, _, action, identifier, detail = mock_save_log.call_args[0]
            assert action == "user_created_createpassword"
            assert identifier == "newuser"
            assert detail["auth"] == "manual"
            assert detail["base_db"] == "Manual"

    def test_create_user_failure(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item"),
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.crear_usuario_si_no_existe.return_value = (None, False)
            mock_integ.ultimo_error = "User creation failed"
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item(accion="create_user")
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)

    def test_enrol_success(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item"),
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.matricular_docente.return_value = {"success": True}
            mock_integ_cls.return_value = mock_integ
            item = _make_item(accion="enrol", course_shortname="CURSE_101", _course_id=42)
            mock_get.return_value = item
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)
            mock_integ.matricular_docente.assert_called_once_with(
                username="IDENTIFIER_001",
                course_shortname="CURSE_101",
                course_map={"CURSE_101": 42},
                email="",
            )

    def test_enrol_failure(self):
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.actualizar_item"),
            patch("app.workers.phases.tarea_item._refrescar_progreso_fase"),
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ = AsyncMock()
            mock_integ.matricular_docente.return_value = {"success": False}
            mock_integ.ultimo_error = "Enrol failed"
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item(accion="enrol", course_shortname="CURSE_101")
            mock_sl.return_value = MagicMock()
            procesar_item_etl(1)

    def test_moodle_overloaded_re_raised(self):
        mock_integ = AsyncMock()
        mock_integ.eliminar_curso.side_effect = ErrorMoodleSobrecargado("overloaded")
        with (
            patch("app.workers.phases.tarea_item.SessionLocal") as mock_sl,
            patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
            patch(
                "app.workers.phases.tarea_item.obtener_servicio_moodle", return_value=_make_moodle()
            ),
            patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
            patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
        ):
            mock_integ_cls.return_value = mock_integ
            mock_get.return_value = _make_item()
            mock_sl.return_value = MagicMock()
            with contextlib.suppress(Exception):
                procesar_item_etl(1)

    def test_create_user_propagates_username_to_pending_enrols(self, test_db):
        """Si create_user descubre un username distinto, se propaga a los enrols."""
        import os

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.modelos import Ejecucion, ItemOperacion
        from app.repositories.repositorio_operaciones import agregar_item, crear_lote

        ex = Ejecucion(
            nombre_archivo="test.xlsx", semestre="2025A", estado="running", modalidad="DISTANCIA"
        )
        test_db.add(ex)
        test_db.commit()
        ex_id = ex.id
        crear_lote(test_db, f"etl_4_enrol_{ex_id}", "enrolments", "enrol", 2, "DISTANCIA")
        agregar_item(
            test_db, f"etl_4_enrol_{ex_id}", "acgonzalezn", {"action": "enrol"}, estado="pending"
        )
        agregar_item(
            test_db, f"etl_4_enrol_{ex_id}", "otrousuario", {"action": "enrol"}, estado="pending"
        )
        test_db.commit()

        # Sesión propia para el worker (process_etl_item la cierra al finalizar).
        engine = create_engine(
            os.environ["DATABASE_URL"], connect_args={"check_same_thread": False}
        )
        Session = sessionmaker(bind=engine)
        worker_db = Session()
        try:
            mock_integ = AsyncMock()
            mock_integ.crear_usuario_si_no_existe.return_value = ("acristinagonzalez", False)
            with (
                patch("app.workers.phases.tarea_item.SessionLocal", return_value=worker_db),
                patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
                patch(
                    "app.workers.phases.tarea_item.obtener_servicio_moodle",
                    return_value=_make_moodle(),
                ),
                patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
                patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
            ):
                mock_integ_cls.return_value = mock_integ
                item = _make_item(accion="create_user", execution_id=ex_id)
                item.identificador = "acgonzalezn"
                mock_get.return_value = item
                procesar_item_etl(1)
        finally:
            worker_db.close()

        check = Session()
        try:
            identifiers = {
                i.identificador
                for i in check.query(ItemOperacion).filter(
                    ItemOperacion.id_lote == f"etl_4_enrol_{ex_id}"
                )
            }
        finally:
            check.close()
        assert "acristinagonzalez" in identifiers
        assert "otrousuario" in identifiers
        assert "acgonzalezn" not in identifiers

    def test_create_user_reused_logs_user_reused_by_email(self, test_db):
        """Cuando create_user reutiliza un usuario existente, se audita el evento."""
        import os

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.db.modelos import Ejecucion, RegistroEjecucion
        from app.repositories.repositorio_operaciones import agregar_item, crear_lote

        ex = Ejecucion(
            nombre_archivo="test.xlsx", semestre="2025A", estado="running", modalidad="DISTANCIA"
        )
        test_db.add(ex)
        test_db.commit()
        ex_id = ex.id
        crear_lote(test_db, f"etl_4_enrol_{ex_id}", "enrolments", "enrol", 1, "DISTANCIA")
        agregar_item(
            test_db, f"etl_4_enrol_{ex_id}", "docente2", {"action": "enrol"}, estado="pending"
        )
        test_db.commit()

        engine = create_engine(
            os.environ["DATABASE_URL"], connect_args={"check_same_thread": False}
        )
        Session = sessionmaker(bind=engine)
        worker_db = Session()
        try:
            mock_integ = AsyncMock()
            mock_integ.crear_usuario_si_no_existe.return_value = ("docente_real", False)
            with (
                patch("app.workers.phases.tarea_item.SessionLocal", return_value=worker_db),
                patch("app.workers.phases.tarea_item.obtener_item") as mock_get,
                patch(
                    "app.workers.phases.tarea_item.obtener_servicio_moodle",
                    return_value=_make_moodle(),
                ),
                patch("app.workers.phases.tarea_item.IntegracionMoodle") as mock_integ_cls,
                patch("app.workers.phases.tarea_item.reclamar_item", return_value=True),
            ):
                mock_integ_cls.return_value = mock_integ
                item = _make_item(accion="create_user", execution_id=ex_id)
                item.identificador = "docente2"
                mock_get.return_value = item
                procesar_item_etl(1)
        finally:
            worker_db.close()

        check = Session()
        try:
            log = (
                check.query(RegistroEjecucion)
                .filter(
                    RegistroEjecucion.ejecucion_id == ex_id,
                    RegistroEjecucion.accion == "user_reused_by_email",
                )
                .first()
            )
        finally:
            check.close()
        assert log is not None
        assert log.identificador == "docente_real"
        assert log.detalle["etl_username"] == "docente2"
        assert log.detalle["enrolments_propagated"] is True


class TestRefreshPhaseProgress:
    def _execution(self, test_db, porcentaje_progreso=None, actualizado_en=None):
        from datetime import UTC, datetime

        from app.db.modelos import Ejecucion

        ex = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025A",
            estado="running",
            modalidad="DISTANCIA",
            porcentaje_progreso=porcentaje_progreso,
            progreso_actualizado_en=actualizado_en or datetime.now(UTC),
        )
        test_db.add(ex)
        test_db.commit()
        return ex

    def test_skips_when_recently_updated(self, test_db):
        from app.workers.phases.tarea_item import _refrescar_progreso_fase

        ex = self._execution(test_db, porcentaje_progreso=50.0)
        with patch("app.pipeline.progreso.calcular_progreso_fase") as mock_cp:
            _refrescar_progreso_fase(ex.id, test_db)
        mock_cp.assert_not_called()

    def test_updates_when_stale(self, test_db):
        from datetime import timedelta

        from app.workers.phases.tarea_item import _refrescar_progreso_fase

        ex = self._execution(test_db, porcentaje_progreso=50.0)
        ex.progreso_actualizado_en = ex.progreso_actualizado_en - timedelta(minutes=5)
        test_db.commit()
        with patch("app.pipeline.progreso.calcular_progreso_fase", return_value=62.0) as mock_cp:
            _refrescar_progreso_fase(ex.id, test_db)
        mock_cp.assert_called_once()
        test_db.refresh(ex)
        assert ex.porcentaje_progreso == 62.0
