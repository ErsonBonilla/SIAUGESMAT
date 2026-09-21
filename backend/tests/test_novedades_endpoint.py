"""
Pruebas del endpoint POST /novedades/compare (validación y mapeo de respuesta).
"""

import io
from unittest.mock import AsyncMock, patch

from fastapi import status


def _excel_bytes():
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["CAT", "PROGRAMA", "SEMESTRE", "GRUPO", "CÓDIGO CURSO"])
    ws.append(["IBAGUE", "0105", "1", "A", "101"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _subir(client, headers, *, semestre="2025B", filename="novedades.xlsx", data=None):
    return client.post(
        "/api/v1/novedades/compare",
        files={
            "file": (
                filename,
                data if data is not None else _excel_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"semester": semestre},
        headers=headers,
    )


class TestNovedadesCompare:
    def test_semestre_invalido(self, client, encabezados_auth):
        response = _subir(client, encabezados_auth, semestre="2025")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_extension_no_permitida(self, client, encabezados_auth):
        response = _subir(client, encabezados_auth, filename="carga.csv", data=b"a,b\n1,2\n")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_no_es_excel(self, client, encabezados_auth):
        response = _subir(client, encabezados_auth, data=b"no es un excel")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.api.v1.endpoints.novedades.detectar_novedades", new_callable=AsyncMock)
    def test_error_de_deteccion(self, mock_detectar, client, encabezados_auth):
        mock_detectar.return_value = ({}, "No se encontró una ejecución previa.")
        response = _subir(client, encabezados_auth)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "ejecución previa" in response.json()["detail"]

    @patch("app.api.v1.endpoints.novedades.detectar_novedades", new_callable=AsyncMock)
    def test_deteccion_exitosa(self, mock_detectar, client, encabezados_auth):
        mock_detectar.return_value = (
            {
                "semester": "2025B",
                "previous_execution_id": 42,
                "previous_filename": "carga_anterior.xlsx",
                "total_compared": 3,
                "novedades": [
                    {
                        "id": "n1",
                        "base_key": "KEY_1",
                        "old_shortname": "OLD",
                        "new_shortname": "NEW",
                        "old_prof_name": "A",
                        "new_prof_name": "B",
                        "course_fullname": "Curso",
                        "action": "hide",
                    }
                ],
            },
            None,
        )
        response = _subir(client, encabezados_auth)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["semester"] == "2025B"
        assert body["previous_execution_id"] == 42
        assert body["total_compared"] == 3
        assert body["novedades"][0]["old_shortname"] == "OLD"
