"""
Pruebas de módulos de servicios sin cobertura previa:
orquestacion (puente API→Celery), validacion_excel, fabrica_moodle y
servicio_novedades (detección de novedades).
"""

import io
from unittest.mock import patch

import pytest

from app.db.modelos import Ejecucion
from app.services.fabrica_moodle import obtener_servicio_moodle
from app.services.orquestacion import (
    encolar_consulta_async,
    encolar_etl,
    encolar_lote_operacion,
    revocar_tarea,
)
from app.services.servicio_novedades import detectar
from app.services.validacion_excel import es_contenido_excel


class TestValidacionExcel:
    def test_excel_zip_valido(self):
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["a", "b"])
        ws.append([1, 2])
        buf = io.BytesIO()
        wb.save(buf)
        assert es_contenido_excel(buf.getvalue()) is True

    def test_ole2_biff(self):
        magic = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        assert es_contenido_excel(magic + b"resto-binario") is True

    def test_basura(self):
        assert es_contenido_excel(b"esto no es un excel") is False

    def test_vacio(self):
        assert es_contenido_excel(b"") is False


class TestFabricaMoodle:
    def test_construye_servicio_con_config(self):
        with (
            patch("app.services.fabrica_moodle.settings") as mock_settings,
            patch("app.services.fabrica_moodle.ServicioMoodle") as mock_sm,
        ):
            mock_settings.obtener_config_moodle.return_value = {
                "token": "tok",
                "url": "http://moodle",
                "version": "3.9",
            }
            obtener_servicio_moodle("DISTANCIA")
            mock_sm.assert_called_once_with(token="tok", base_url="http://moodle", version="3.9")


class TestOrquestacion:
    def test_encolar_etl(self):
        with patch("app.services.orquestacion.procesar_archivo_etl") as mock_task:
            mock_task.delay.return_value = "resultado"
            result = encolar_etl(1, "/tmp/x.xlsx", "2025B")
            mock_task.delay.assert_called_once_with(1, "/tmp/x.xlsx", "2025B")
            assert result == "resultado"

    def test_encolar_consulta(self):
        with patch("app.services.orquestacion.ejecutar_consulta") as mock_task:
            encolar_consulta_async("task-1")
            mock_task.delay.assert_called_once_with("task-1")

    def test_encolar_lote(self):
        with patch("app.services.orquestacion.procesar_lote_operacion") as mock_task:
            encolar_lote_operacion("batch-1")
            mock_task.delay.assert_called_once_with("batch-1")

    def test_revocar_tarea(self):
        with patch("app.services.orquestacion.celery_app") as mock_app:
            revocar_tarea("task-1", terminate=True)
            mock_app.control.revoke.assert_called_once_with("task-1", terminate=True)


class TestServicioNovedades:
    @pytest.mark.asyncio
    async def test_sin_cursos_nuevos(self, test_db):
        with patch(
            "app.services.servicio_novedades.ServicioETL.procesar",
            return_value={"courses": []},
        ):
            result, error = await detectar(test_db, "2025B", "DISTANCIA", "/tmp/n.xlsx")
        assert result == {}
        assert "no contiene cursos" in error

    @pytest.mark.asyncio
    async def test_sin_ejecucion_previa(self, test_db):
        with patch(
            "app.services.servicio_novedades.ServicioETL.procesar",
            return_value={"courses": [{"shortname": "X"}]},
        ):
            result, error = await detectar(test_db, "2025B", "DISTANCIA", "/tmp/n.xlsx")
        assert result == {}
        assert "ejecución previa" in error

    @pytest.mark.asyncio
    async def test_exito(self, test_db):
        ej = Ejecucion(
            nombre_archivo="old.xlsx",
            semestre="2025B",
            modo="both",
            estado="completed",
            modalidad="DISTANCIA",
        )
        test_db.add(ej)
        test_db.commit()

        novedades = [
            {
                "id": "n1",
                "base_key": "KEY",
                "old_shortname": "OLD",
                "new_shortname": "NEW",
                "old_prof_name": "A",
                "new_prof_name": "B",
                "course_fullname": "Curso",
                "action": "hide",
            }
        ]
        stats = {"total_compared": 1}
        with (
            patch(
                "app.services.servicio_novedades.ServicioETL.procesar",
                side_effect=[{"courses": [{"shortname": "X"}]}, {"courses": [{"shortname": "X"}]}],
            ),
            patch("app.services.servicio_novedades.os.path.exists", return_value=True),
            patch(
                "app.services.servicio_novedades.detectar_novedades",
                return_value=(novedades, stats),
            ),
        ):
            result, error = await detectar(test_db, "2025B", "DISTANCIA", "/tmp/n.xlsx")

        assert error is None
        assert result["previous_execution_id"] == ej.id
        assert result["previous_filename"] == "old.xlsx"
        assert result["total_compared"] == 1
        assert result["novedades"][0]["old_shortname"] == "OLD"
