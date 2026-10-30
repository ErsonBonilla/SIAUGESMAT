import uuid
from unittest.mock import patch

from app.repositories.repositorio_consultas import crear_consulta, marcar_consulta_completada


class TestEnqueueQuery:
    def test_unknown_entity(self, client, encabezados_auth):
        resp = client.post("/api/v1/queries/invalid", json={}, headers=encabezados_auth)
        assert resp.status_code == 400

    def test_successful_enqueue(self, client, encabezados_auth, test_db):
        with patch("app.api.v1.endpoints.consultas.encolar_consulta_async") as mock_delay:
            resp = client.post("/api/v1/queries/courses", json={}, headers=encabezados_auth)
            assert resp.status_code == 200
            data = resp.json()
            assert data["entity"] == "courses"
            assert data["status"] == "pending"
            assert uuid.UUID(data["task_id"])
            mock_delay.assert_called_once_with(data["task_id"])

    def test_enqueue_duplicate_emails(self, client, encabezados_auth, test_db):
        with patch("app.api.v1.endpoints.consultas.encolar_consulta_async") as mock_delay:
            resp = client.post(
                "/api/v1/queries/duplicate_emails", json={}, headers=encabezados_auth
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["entity"] == "duplicate_emails"
            assert data["status"] == "pending"
            mock_delay.assert_called_once_with(data["task_id"])

    def test_requires_auth(self, client):
        resp = client.post("/api/v1/queries/courses", json={})
        assert resp.status_code == 401


class TestGetTaskStatus:
    def test_not_found(self, client, encabezados_auth):
        resp = client.get("/api/v1/queries/tasks/nonexistent", headers=encabezados_auth)
        assert resp.status_code == 404

    def test_returns_task(self, client, encabezados_auth, test_db):
        crear_consulta(test_db, "test-task-id", "courses", {}, "DISTANCIA")
        resp = client.get("/api/v1/queries/tasks/test-task-id", headers=encabezados_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "test-task-id"
        assert data["status"] == "pending"


class TestDownloadCsv:
    def test_not_found(self, client, encabezados_auth):
        resp = client.get("/api/v1/queries/tasks/nonexistent/download", headers=encabezados_auth)
        assert resp.status_code == 404

    def test_not_completed(self, client, encabezados_auth, test_db):
        crear_consulta(test_db, "test-task-id", "courses", {}, "DISTANCIA")
        resp = client.get("/api/v1/queries/tasks/test-task-id/download", headers=encabezados_auth)
        assert resp.status_code == 409

    def test_duplicate_emails_csv(self, client, encabezados_auth, test_db):
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
        crear_consulta(test_db, "task-dup", "duplicate_emails", {}, "DISTANCIA")
        marcar_consulta_completada(test_db, "task-dup", rows, len(rows))
        resp = client.get("/api/v1/queries/tasks/task-dup/download", headers=encabezados_auth)
        assert resp.status_code == 200
        content = resp.content.decode("utf-8-sig")
        assert "Email,Username,Nombres,Apellidos,ID Moodle,Nº de cuentas" in content
        assert "a@ut.edu.co,u1,Ana,Uno,1,2" in content

    def test_inactive_teachers_csv(self, client, encabezados_auth, test_db):
        rows = [
            {
                "cat_shortname": "IBA",
                "cat_name": "IBAGUE",
                "semester_shortname": "IBA_0854_sIV",
                "semester_name": "SEMESTRE IV",
                "program_shortname": "IBA_0854",
                "program_name": "ADMIN FINANCIERA",
                "course_shortname": "IBA_0854_sIV_2022481_G-1",
                "course_name": "FINANZAS I",
                "username": "doc1",
                "teacher_name": "Juan Perez",
                "email": "doc1@ut.edu.co",
                "last_access": 0,
                "days_since_last_access": 0,
            }
        ]
        crear_consulta(test_db, "task-inact", "inactive_teachers", {"days": 15}, "DISTANCIA")
        marcar_consulta_completada(test_db, "task-inact", rows, len(rows))
        resp = client.get("/api/v1/queries/tasks/task-inact/download", headers=encabezados_auth)
        assert resp.status_code == 200
        content = resp.content.decode("utf-8-sig")
        assert (
            "Shortname CAT,Nombre CAT,Shortname Semestre,Nombre Semestre,"
            "Shortname Programa,Nombre Programa,Shortname Curso,Curso,"
            "Username,Docente,Correo,Último acceso,Días sin acceso"
        ) in content
        assert (
            "IBA,IBAGUE,IBA_0854_sIV,SEMESTRE IV,IBA_0854,ADMIN FINANCIERA,"
            "IBA_0854_sIV_2022481_G-1,FINANZAS I,doc1,Juan Perez,doc1@ut.edu.co,Nunca,Nunca"
        ) in content
