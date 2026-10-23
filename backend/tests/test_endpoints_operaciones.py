"""
Pruebas de endpoints de operaciones sin cobertura previa:
- GET /operations/batches y GET /operations/analytics (listado_lotes)
- Rutas CSV de operaciones masivas (courses/visibility, users/create-csv,
  categories/create-csv, categories/upload-csv, users/upload-csv).
"""

from unittest.mock import patch

from fastapi import status

from app.db.modelos import LoteOperacion


def _csv(bytes_contenido: bytes, nombre="archivo.csv") -> dict:
    return {"file": (nombre, bytes_contenido, "text/csv")}


class TestListadoLotes:
    def test_batches_vacio(self, client, encabezados_auth):
        response = client.get("/api/v1/operations/batches", headers=encabezados_auth)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_batches_con_lote(self, client, encabezados_auth, test_db):
        test_db.add(
            LoteOperacion(
                id_lote="b1",
                tipo_entidad="courses",
                accion="delete",
                total=2,
                completados=1,
                fallidos=0,
                modalidad="DISTANCIA",
            )
        )
        test_db.commit()

        response = client.get("/api/v1/operations/batches", headers=encabezados_auth)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["batch_id"] == "b1"
        assert body["items"][0]["entity_type"] == "courses"
        assert body["items"][0]["action"] == "delete"

    def test_analytics_vacio(self, client, encabezados_auth):
        response = client.get("/api/v1/operations/analytics", headers=encabezados_auth)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["history"] == []


class TestCsvOperaciones:
    @patch("app.api.v1.helpers.manejador_subida.encolar_lote_operacion")
    def test_eliminar_categorias_csv(self, mock_encolar, client, encabezados_auth):
        response = client.post(
            "/api/v1/operations/categories/upload-csv",
            files=_csv(b"idnumber\nCAT_01\n"),
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["entity_type"] == "categories"
        assert body["action"] == "delete"
        assert body["total"] == 1
        mock_encolar.assert_called_once()

    @patch("app.api.v1.helpers.manejador_subida.encolar_lote_operacion")
    def test_eliminar_usuarios_csv(self, mock_encolar, client, encabezados_auth):
        response = client.post(
            "/api/v1/operations/users/upload-csv",
            files=_csv(b"username\nuser1\n"),
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["entity_type"] == "users"

    @patch("app.api.v1.helpers.manejador_subida.encolar_lote_operacion")
    def test_visibilidad_show(self, mock_encolar, client, encabezados_auth):
        response = client.post(
            "/api/v1/operations/courses/visibility?visibility=hide",
            files=_csv(b"shortname\nCURSE_101\n"),
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["action"] == "visibility"

    def test_visibilidad_invalida(self, client, encabezados_auth):
        response = client.post(
            "/api/v1/operations/courses/visibility?visibility=invalid",
            files=_csv(b"shortname\nCURSE_101\n"),
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("app.api.v1.helpers.manejador_subida.encolar_lote_operacion")
    def test_crear_usuarios_csv_con_default_role(self, mock_encolar, client, encabezados_auth):
        csv = "username,firstname,lastname,email\njdoe,John,Doe,jdoe@test.com\n"
        response = client.post(
            "/api/v1/operations/users/create-csv?default_role=teacher",
            files=_csv(csv.encode()),
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["action"] == "create"

    @patch("app.api.v1.helpers.manejador_subida.encolar_lote_operacion")
    def test_crear_categorias_csv(self, mock_encolar, client, encabezados_auth):
        csv = "name,idnumber\nCat One,CAT_01\n"
        response = client.post(
            "/api/v1/operations/categories/create-csv",
            files=_csv(csv.encode()),
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["entity_type"] == "categories"

    def test_crear_usuarios_sin_role(self, client, encabezados_auth):
        csv = "username,firstname,lastname,email\njdoe,John,Doe,jdoe@test.com\n"
        response = client.post(
            "/api/v1/operations/users/create-csv",
            files=_csv(csv.encode()),
            headers=encabezados_auth,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
