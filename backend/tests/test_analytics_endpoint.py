from unittest.mock import patch

import pytest

from app.schemas.analytics import SemaphoreStatus, LatestExecution


class TestGetHistory:
    def test_returns_list(self, client, auth_headers):
        with patch("app.api.v1.endpoints.analytics.get_history_metrics") as mock:
            mock.return_value = []
            resp = client.get("/api/v1/analytics/history", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json() == []

    def test_internal_error(self, client, auth_headers):
        with patch("app.api.v1.endpoints.analytics.get_history_metrics", side_effect=Exception("DB error")):
            resp = client.get("/api/v1/analytics/history", headers=auth_headers)
            assert resp.status_code == 500


class TestGetSemaphore:
    def test_returns_status(self, client, auth_headers):
        with patch("app.api.v1.endpoints.analytics.get_semaphore_status") as mock:
            mock.return_value = SemaphoreStatus(
                semester="2025A", status="green", error_rate=0.5, avg_duration=120.0, message="OK",
            )
            resp = client.get("/api/v1/analytics/semaphore", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "green"


class TestGetLatestExecution:
    def test_returns_data(self, client, auth_headers):
        with patch("app.api.v1.endpoints.analytics.get_latest_execution_data") as mock:
            mock.return_value = LatestExecution(
                id=1, semester="2025A", filename="test.csv", status="completed",
                errors_count=0, error_rate=0.0, semaphore="green",
            )
            resp = client.get("/api/v1/analytics/latest", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["semester"] == "2025A"

    def test_not_found(self, client, auth_headers):
        with patch("app.api.v1.endpoints.analytics.get_latest_execution_data", side_effect=ValueError("No executions")):
            resp = client.get("/api/v1/analytics/latest", headers=auth_headers)
            assert resp.status_code == 404
