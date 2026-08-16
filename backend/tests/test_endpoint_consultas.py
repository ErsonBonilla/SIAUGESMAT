import uuid
from unittest.mock import patch

from app.repositories.query_repo import create_query, set_query_completed


class TestEnqueueQuery:
    def test_unknown_entity(self, client, auth_headers):
        resp = client.post("/api/v1/queries/invalid", json={}, headers=auth_headers)
        assert resp.status_code == 400

    def test_successful_enqueue(self, client, auth_headers, test_db):
        with patch("app.api.v1.endpoints.queries.enqueue_async_query") as mock_delay:
            resp = client.post("/api/v1/queries/courses", json={}, headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["entity"] == "courses"
            assert data["status"] == "pending"
            assert uuid.UUID(data["task_id"])
            mock_delay.assert_called_once_with(data["task_id"])

    def test_enqueue_duplicate_emails(self, client, auth_headers, test_db):
        with patch("app.api.v1.endpoints.queries.enqueue_async_query") as mock_delay:
            resp = client.post("/api/v1/queries/duplicate_emails", json={}, headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["entity"] == "duplicate_emails"
            assert data["status"] == "pending"
            mock_delay.assert_called_once_with(data["task_id"])

    def test_requires_auth(self, client):
        resp = client.post("/api/v1/queries/courses", json={})
        assert resp.status_code == 401


class TestGetTaskStatus:
    def test_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/queries/tasks/nonexistent", headers=auth_headers)
        assert resp.status_code == 404

    def test_returns_task(self, client, auth_headers, test_db):
        create_query(test_db, "test-task-id", "courses", {}, "DISTANCIA")
        resp = client.get("/api/v1/queries/tasks/test-task-id", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "pending"


class TestDownloadCsv:
    def test_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/queries/tasks/nonexistent/download", headers=auth_headers)
        assert resp.status_code == 404

    def test_not_completed(self, client, auth_headers, test_db):
        create_query(test_db, "test-task-id", "courses", {}, "DISTANCIA")
        resp = client.get("/api/v1/queries/tasks/test-task-id/download", headers=auth_headers)
        assert resp.status_code == 409

    def test_duplicate_emails_csv(self, client, auth_headers, test_db):
        rows = [
            {
                "email": "a@ut.edu.co",
                "username": "u1",
                "firstname": "Ana",
                "lastname": "Uno",
                "user_id": 1,
                "duplicate_count": 2,
            },
            {
                "email": "a@ut.edu.co",
                "username": "u2",
                "firstname": "Bruno",
                "lastname": "Dos",
                "user_id": 2,
                "duplicate_count": 2,
            },
        ]
        create_query(test_db, "task-dup", "duplicate_emails", {}, "DISTANCIA")
        set_query_completed(test_db, "task-dup", rows, len(rows))
        resp = client.get("/api/v1/queries/tasks/task-dup/download", headers=auth_headers)
        assert resp.status_code == 200
        content = resp.content.decode("utf-8-sig")
        assert "Email,Username,Nombres,Apellidos,ID Moodle,Nº de cuentas" in content
        assert "a@ut.edu.co,u1,Ana,Uno,1,2" in content
