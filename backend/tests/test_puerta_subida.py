"""
Pruebas del control de concurrencia: no se permite subir un nuevo archivo
(Excel ETL o CSV de operaciones) mientras haya un proceso en curso para la
misma modalidad.
"""

import io

import pytest
from fastapi import status

from app.db.modelos import Ejecucion, ItemOperacion, LoteOperacion


def _valid_excel_bytes():
    """Retorna un Excel .xlsx mínimo válido en memoria."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(
        [
            "CAT",
            "PROGRAMA",
            "SEMESTRE",
            "GRUPO",
            "CÓDIGO CURSO",
            "CURSO",
            "DOCENTE",
            "CEDULA",
            "CORREO INSTITUCIONAL",
            "CORREO PERSONAL",
            "PERFIL DEL DOCENTE",
            "MODALIDAD",
        ]
    )
    ws.append(
        [
            "IBAGUE",
            "0105 - LICENCIATURA EN MATEMATICAS",
            "1",
            "A",
            "101",
            "CALCULO I",
            "PEREZ, JUAN",
            "12345",
            "juan@ut.edu.co",
            "juan@gmail.com",
            "Perfil A",
            "PRESENCIAL",
        ]
    )
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


UPLOAD_URL = "/api/v1/upload"


def _upload_solicitar(client, encabezados_auth, *, modalidad="DISTANCIA"):
    return client.post(
        UPLOAD_URL,
        files={
            "file": (
                "test.xlsx",
                _valid_excel_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data={"semester": "2025B", "mode": "both", "modalidad": modalidad},
        headers=encabezados_auth,
    )


class TestUploadGateExecution:
    """Bloqueo de subida de Excel mientras hay una ejecución ETL en curso."""

    @pytest.mark.parametrize("active_status", ["queued", "running", "paused", "review_required"])
    def test_upload_blocked_when_execution_active(
        self, client, encabezados_auth, test_db, active_status
    ):
        exec_active = Ejecucion(
            nombre_archivo="otra.xlsx",
            semestre="2025B",
            modo="both",
            estado=active_status,
            modalidad="DISTANCIA",
        )
        test_db.add(exec_active)
        test_db.commit()

        response = _upload_solicitar(client, encabezados_auth)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "proceso en curso" in response.json()["detail"].lower()

    def test_upload_blocked_only_same_modalidad(self, client, encabezados_auth, test_db):
        exec_active = Ejecucion(
            nombre_archivo="otra.xlsx",
            semestre="2025B",
            modo="both",
            estado="running",
            modalidad="PRESENCIAL",
        )
        test_db.add(exec_active)
        test_db.commit()

        response = _upload_solicitar(client, encabezados_auth, modalidad="DISTANCIA")
        assert response.status_code == status.HTTP_201_CREATED

    def test_upload_allowed_when_only_completed(self, client, encabezados_auth, test_db):
        done = Ejecucion(
            nombre_archivo="otra.xlsx",
            semestre="2025B",
            modo="both",
            estado="completed",
            modalidad="DISTANCIA",
        )
        test_db.add(done)
        test_db.commit()

        response = _upload_solicitar(client, encabezados_auth)
        assert response.status_code == status.HTTP_201_CREATED

    def test_upload_allowed_when_nothing_active(self, client, encabezados_auth):
        response = _upload_solicitar(client, encabezados_auth)
        assert response.status_code == status.HTTP_201_CREATED


class TestUploadGateBatch:
    """Bloqueo de subida de Excel mientras hay un lote CSV en curso."""

    def _active_batch(self, test_db):
        batch = LoteOperacion(
            id_lote="batch-activo-1",
            tipo_entidad="courses",
            accion="delete",
            total=1,
            modalidad="DISTANCIA",
        )
        test_db.add(batch)
        item = ItemOperacion(id_lote=batch.id_lote, identificador="X", estado="processing")
        test_db.add(item)
        test_db.commit()
        return batch

    def test_upload_blocked_when_batch_active(self, client, encabezados_auth, test_db):
        self._active_batch(test_db)
        response = _upload_solicitar(client, encabezados_auth)
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "proceso en curso" in response.json()["detail"].lower()


class TestStartProcessGate:
    """No se puede iniciar un proceso ETL si otra ejecución del mismo módulo corre."""

    def test_process_blocked_when_other_active(self, client, encabezados_auth, test_db):
        other = Ejecucion(
            nombre_archivo="otra.xlsx",
            semestre="2025B",
            modo="both",
            estado="running",
            modalidad="DISTANCIA",
        )
        test_db.add(other)
        test_db.commit()

        exec_pending = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025B",
            modo="both",
            estado="pending",
            modalidad="DISTANCIA",
        )
        test_db.add(exec_pending)
        test_db.commit()

        response = client.post(
            f"/api/v1/jobs/{exec_pending.id}/process",
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "proceso en ejecución" in response.json()["detail"].lower()

    def test_process_allowed_without_other_active(self, client, encabezados_auth, test_db):
        from unittest.mock import patch

        exec_pending = Ejecucion(
            nombre_archivo="test.xlsx",
            semestre="2025B",
            modo="both",
            estado="pending",
            modalidad="DISTANCIA",
        )
        test_db.add(exec_pending)
        test_db.commit()

        with (
            patch("app.api.v1.endpoints.trabajos.encolar_etl") as mock_delay,
            patch("app.api.v1.endpoints.trabajos.os.path.isfile", return_value=True),
        ):
            mock_delay.return_value = type("AsyncResult", (), {"id": "mock-task-123"})()
            response = client.post(
                f"/api/v1/jobs/{exec_pending.id}/process",
                headers=encabezados_auth,
            )
        assert response.status_code == status.HTTP_202_ACCEPTED


class TestCsvUploadGate:
    """Bloqueo de subida de CSV de operaciones mientras hay un proceso en curso."""

    def test_csv_blocked_when_execution_active(self, client, encabezados_auth, test_db):
        exec_active = Ejecucion(
            nombre_archivo="otra.xlsx",
            semestre="2025B",
            modo="both",
            estado="running",
            modalidad="DISTANCIA",
        )
        test_db.add(exec_active)
        test_db.commit()

        response = client.post(
            "/api/v1/operations/courses/upload-csv",
            files={"file": ("cursos.csv", b"shortname\nXYZ", "text/csv")},
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_csv_allowed_without_active(self, client, encabezados_auth):
        response = client.post(
            "/api/v1/operations/courses/upload-csv",
            files={"file": ("cursos.csv", b"shortname\nXYZ", "text/csv")},
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_200_OK


class TestUploadStatusEndpoint:
    """GET /api/v1/upload/status informa al frontend si se puede subir."""

    def test_status_allowed(self, client, encabezados_auth):
        response = client.get(f"{UPLOAD_URL}/status", headers=encabezados_auth)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["allowed"] is True
        assert body["execution"] is None
        assert body["batch"] is None

    def test_status_blocked_by_execution(self, client, encabezados_auth, test_db):
        exec_active = Ejecucion(
            nombre_archivo="otra.xlsx",
            semestre="2025B",
            modo="both",
            estado="running",
            modalidad="DISTANCIA",
        )
        test_db.add(exec_active)
        test_db.commit()

        response = client.get(f"{UPLOAD_URL}/status", headers=encabezados_auth)
        body = response.json()
        assert body["allowed"] is False
        assert body["execution"]["id"] == exec_active.id
        assert body["execution"]["status"] == "running"

    def test_status_blocked_by_batch(self, client, encabezados_auth, test_db):
        batch = LoteOperacion(
            id_lote="batch-activo-2",
            tipo_entidad="users",
            accion="create",
            total=1,
            modalidad="DISTANCIA",
        )
        test_db.add(batch)
        item = ItemOperacion(id_lote=batch.id_lote, identificador="u1", estado="pending")
        test_db.add(item)
        test_db.commit()

        response = client.get(f"{UPLOAD_URL}/status", headers=encabezados_auth)
        body = response.json()
        assert body["allowed"] is False
        assert body["batch"]["batch_id"] == "batch-activo-2"
