from unittest.mock import patch

from app.schemas.analitica import EjecucionReciente, EstadoSemaforo


class TestGetHistory:
    def test_returns_list(self, client, encabezados_auth):
        with patch("app.api.v1.endpoints.analitica.obtener_metricas_historial") as mock:
            mock.return_value = []
            resp = client.get("/api/v1/analytics/history", headers=encabezados_auth)
            assert resp.status_code == 200
            assert resp.json() == []

    def test_internal_error(self, client, encabezados_auth):
        with patch(
            "app.api.v1.endpoints.analitica.obtener_metricas_historial",
            side_effect=Exception("DB error"),
        ):
            resp = client.get("/api/v1/analytics/history", headers=encabezados_auth)
            assert resp.status_code == 500


class TestGetSemaphore:
    def test_returns_status(self, client, encabezados_auth):
        with patch("app.api.v1.endpoints.analitica.obtener_estado_semaforo") as mock:
            mock.return_value = EstadoSemaforo(
                semester="2025A",
                status="green",
                error_rate=0.5,
                avg_duration=120.0,
                message="OK",
            )
            resp = client.get("/api/v1/analytics/semaphore", headers=encabezados_auth)
            assert resp.status_code == 200
            assert resp.json()["status"] == "green"


class TestGetLatestExecution:
    def test_returns_data(self, client, encabezados_auth):
        with patch("app.api.v1.endpoints.analitica.obtener_datos_ejecucion_reciente") as mock:
            mock.return_value = EjecucionReciente(
                id=1,
                semester="2025A",
                filename="test.csv",
                status="completed",
                errors_count=0,
                error_rate=0.0,
                semaphore="green",
            )
            resp = client.get("/api/v1/analytics/latest", headers=encabezados_auth)
            assert resp.status_code == 200
            assert resp.json()["semester"] == "2025A"

    def test_not_found(self, client, encabezados_auth):
        with patch(
            "app.api.v1.endpoints.analitica.obtener_datos_ejecucion_reciente",
            side_effect=ValueError("No executions"),
        ):
            resp = client.get("/api/v1/analytics/latest", headers=encabezados_auth)
            assert resp.status_code == 404
