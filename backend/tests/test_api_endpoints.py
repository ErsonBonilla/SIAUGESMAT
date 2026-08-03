"""
Pruebas de integración para endpoints de la API REST.

Cubre los endpoints de subida (upload), jobs, reports y charts,
utilizando mocks para aislar la comunicación externa con Moodle.
"""

import io
import os
import struct
import tempfile
import zlib
from unittest.mock import patch

from fastapi import status

from app.core.config import settings
from app.db.models import Execution
from app.services.reports import ReportService


def _minimal_png() -> bytes:
    """Retorna un PNG mínimo de 1x1 pixel rojo."""
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack('>I', zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff)
    ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + ihdr_crc
    raw = b'\x00\xff\x00\x00'
    compressed = zlib.compress(raw)
    idat_crc = struct.pack('>I', zlib.crc32(b'IDAT' + compressed) & 0xffffffff)
    idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + idat_crc
    iend_crc = struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff)
    iend = struct.pack('>I', 0) + b'IEND' + iend_crc
    return sig + ihdr + idat + iend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_valid_excel_bytes():
    """Retorna un archivo Excel .xlsx mínimo válido en memoria."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    # Encabezados esperados por el ETL
    headers = ["CAT", "PROGRAMA", "SEMESTRE", "GRUPO", "CÓDIGO CURSO",
               "CURSO", "DOCENTE", "CEDULA", "CORREO INSTITUCIONAL",
               "CORREO PERSONAL", "PERFIL DEL DOCENTE", "MODALIDAD"]
    ws.append(headers)
    ws.append(["IBAGUE", "0105 - LICENCIATURA EN MATEMATICAS", "1", "A",
               "101", "CALCULO I", "PEREZ, JUAN", "12345",
               "juan@ut.edu.co", "juan@gmail.com", "Perfil A", "PRESENCIAL"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------
class TestUploadEndpoint:

    UPLOAD_URL = "/api/v1/upload"

    def test_upload_invalid_extension(self, client, auth_headers):
        """Archivo .csv debe ser rechazado."""
        response = client.post(
            self.UPLOAD_URL,
            files={"file": ("test.csv", b"datos", "text/csv")},
            data={"semester": "2025B", "mode": "both", "modalidad": "DISTANCIA"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_invalid_semester_format(self, client, auth_headers):
        """Semestre con formato inválido debe ser rechazado."""
        response = client.post(
            self.UPLOAD_URL,
            files={"file": ("test.xlsx", b"dummy", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"semester": "2025", "mode": "both", "modalidad": "DISTANCIA"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "semestre" in response.json()["detail"].lower()

    def test_upload_invalid_mode(self, client, auth_headers):
        """Modo inválido debe ser rechazado."""
        response = client.post(
            self.UPLOAD_URL,
            files={"file": ("test.xlsx", b"dummy", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"semester": "2025B", "mode": "invalid", "modalidad": "DISTANCIA"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "modo" in response.json()["detail"].lower()

    def test_upload_invalid_modalidad(self, client, auth_headers):
        """Modalidad inválida debe ser rechazada."""
        response = client.post(
            self.UPLOAD_URL,
            files={"file": ("test.xlsx", b"dummy", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"semester": "2025B", "mode": "both", "modalidad": "INEXISTENTE"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "modalidad" in response.json()["detail"].lower()

    def test_upload_requires_auth(self, client):
        """Subir archivo sin autenticación debe retornar 401."""
        response = client.post(
            self.UPLOAD_URL,
            files={"file": ("test.xlsx", b"dummy", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"semester": "2025B", "mode": "both", "modalidad": "DISTANCIA"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Jobs endpoint
# ---------------------------------------------------------------------------
class TestJobsEndpoint:

    JOBS_URL = "/api/v1/jobs"

    def test_list_executions(self, client, auth_headers, test_db):
        """Listar ejecuciones debe retornar 200."""
        exec = Execution(
            filename="test.xlsx", semester="2025B", mode="both",
            status="completed", modalidad="DISTANCIA",
        )
        test_db.add(exec)
        test_db.commit()

        response = client.get(self.JOBS_URL, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    def test_get_execution_detail(self, client, auth_headers, test_db):
        """Obtener detalle de una ejecución debe retornar 200."""
        exec = Execution(
            filename="test.xlsx", semester="2025B", mode="both",
            status="completed", modalidad="DISTANCIA",
        )
        test_db.add(exec)
        test_db.commit()

        response = client.get(f"{self.JOBS_URL}/{exec.id}", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == exec.id
        assert data["status"] == "completed"

    def test_get_execution_not_found(self, client, auth_headers):
        """Ejecución inexistente debe retornar 404."""
        response = client.get(f"{self.JOBS_URL}/99999", headers=auth_headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_start_process(self, client, auth_headers, test_db):
        """Iniciar procesamiento de ejecución pendiente debe retornar 202."""
        exec = Execution(
            filename="test.xlsx", semester="2025B", mode="both",
            status="pending", modalidad="DISTANCIA",
        )
        test_db.add(exec)
        test_db.commit()

        with (
            patch("app.api.v1.endpoints.jobs.process_etl_file.delay") as mock_delay,
            patch("app.api.v1.endpoints.jobs.os.path.isfile", return_value=True),
        ):
            mock_delay.return_value = None
            mock_delay.return_value = type("AsyncResult", (), {"id": "mock-task-123"})()
            response = client.post(
                f"{self.JOBS_URL}/{exec.id}/process", headers=auth_headers,
            )
            assert response.status_code == status.HTTP_202_ACCEPTED
            mock_delay.assert_called_once()

    def test_process_already_completed(self, client, auth_headers, test_db):
        """Procesar una ejecución ya completada debe retornar 409."""
        exec = Execution(
            filename="test.xlsx", semester="2025B", mode="both",
            status="completed", modalidad="DISTANCIA",
        )
        test_db.add(exec)
        test_db.commit()

        response = client.post(
            f"{self.JOBS_URL}/{exec.id}/process", headers=auth_headers,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_jobs_requires_auth(self, client):
        """Listar ejecuciones sin auth debe retornar 401."""
        response = client.get(self.JOBS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_process_requires_auth(self, client):
        """Iniciar proceso sin auth debe retornar 401."""
        response = client.post(f"{self.JOBS_URL}/1/process")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Reports endpoint
# ---------------------------------------------------------------------------
class TestReportsEndpoint:

    REPORTS_URL = "/api/v1/reports"

    def test_list_reports(self, client, auth_headers, test_db):
        """Listar reportes de una ejecución debe retornar 200."""
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(settings, "REPORT_DIR", tmpdir):
            # Crear directorio simulado de reportes
            report_dir = os.path.join(tmpdir, "exec_1_20250101_120000")
            os.makedirs(report_dir)
            # Crear CSVs simulados con nombres reales
            for name in ReportService.REPORT_NAMES.values():
                open(os.path.join(report_dir, name), "w").close()

            exec = Execution(
                filename="test.xlsx", semester="2025B", mode="both",
                status="completed", modalidad="DISTANCIA",
                report_dir=report_dir,
            )
            test_db.add(exec)
            test_db.commit()

            response = client.get(
                f"{self.REPORTS_URL}/{exec.id}/reports", headers=auth_headers,
            )
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data["reports"]) == len(ReportService.REPORT_NAMES)

    def test_list_reports_no_reports(self, client, auth_headers, test_db):
        """Ejecución sin reportes debe retornar 404."""
        exec = Execution(
            filename="test.xlsx", semester="2025B", mode="both",
            status="pending", modalidad="DISTANCIA",
        )
        test_db.add(exec)
        test_db.commit()

        response = client.get(
            f"{self.REPORTS_URL}/{exec.id}/reports", headers=auth_headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_download_zip(self, client, auth_headers, test_db):
        """Descargar ZIP de reportes debe retornar 200."""
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(settings, "REPORT_DIR", tmpdir):
            report_dir = os.path.join(tmpdir, "exec_2_20250101_120000")
            os.makedirs(report_dir)
            open(os.path.join(report_dir, "test.csv"), "w").close()
            zip_path = report_dir + ".zip"
            import zipfile
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.write(os.path.join(report_dir, "test.csv"), "test.csv")

            exec = Execution(
                filename="test.xlsx", semester="2025B", mode="both",
                status="completed", modalidad="DISTANCIA",
                report_dir=report_dir,
            )
            test_db.add(exec)
            test_db.commit()

            response = client.get(
                f"{self.REPORTS_URL}/{exec.id}/reports/download", headers=auth_headers,
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "application/zip"


# ---------------------------------------------------------------------------
# Charts endpoint
# ---------------------------------------------------------------------------
class TestChartsEndpoint:

    CHARTS_URL = "/api/v1/analytics/executions"

    def test_get_charts_list(self, client, auth_headers, test_db):
        """Listar gráficas disponibles para una ejecución debe retornar 200."""
        exec = Execution(
            filename="test.xlsx", semester="2025B", mode="both",
            status="completed", modalidad="DISTANCIA",
        )
        test_db.add(exec)
        test_db.commit()

        response = client.get(
            f"{self.CHARTS_URL}/{exec.id}/charts", headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["charts"]) > 0
        assert all("id" in c and "title" in c for c in data["charts"])

    def test_get_chart_data(self, client, auth_headers, test_db):
        """Obtener datos JSON de una gráfica debe retornar 200."""
        exec = Execution(
            filename="test.xlsx", semester="2025B", mode="both",
            status="completed", modalidad="DISTANCIA",
        )
        test_db.add(exec)
        test_db.commit()

        response = client.get(
            f"{self.CHARTS_URL}/{exec.id}/charts/resumen_ejecutivo",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)
