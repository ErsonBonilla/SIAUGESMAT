"""
Pruebas unitarias para el endpoint de autenticación (auth.py).

Valida los flujos de inicio de sesión contra Moodle y la generación de
tokens JWT locales, usando mocks para aislar la comunicación externa.
"""

from unittest.mock import patch

from fastapi import status
from jose import jwt

from app.core.config import settings


# ---------------------------------------------------------------------------
# Inicio de sesión exitoso
# ---------------------------------------------------------------------------
def test_login_success(client):
    """Unas credenciales correctas deben retornar 200 y un JWT válido."""
    # Mockeamos las funciones internas de auth para evitar llamadas reales a Moodle
    with (
        patch("app.core.config.Settings.get_moodle_config") as mock_cfg,
        patch("app.api.v1.endpoints.auth._get_moodle_token") as mock_token,
        patch("app.api.v1.endpoints.auth._check_moodle_permissions") as mock_perm,
    ):
        mock_cfg.return_value = {"url": "http://fake.moodle.com", "token": "fake", "version": "3.9"}
        mock_token.return_value = "fake_moodle_token"
        mock_perm.return_value = 42

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "profesor", "password": "secreta", "modalidad": "DISTANCIA"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == 42
        assert data["username"] == "profesor"

        payload = jwt.decode(
            data["access_token"],
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["sub"] == "42"
        assert payload["username"] == "profesor"
        assert payload["modalidad"] == "DISTANCIA"
        assert data["modalidad"] == "DISTANCIA"


# ---------------------------------------------------------------------------
# Credenciales inválidas
# ---------------------------------------------------------------------------
def test_login_invalid_credentials(client):
    """Si Moodle rechaza las credenciales, debe retornar 401."""
    with (
        patch("app.core.config.Settings.get_moodle_config") as mock_cfg,
        patch("app.api.v1.endpoints.auth._get_moodle_token") as mock_token,
    ):
        mock_cfg.return_value = {"url": "http://fake.moodle.com", "token": "fake", "version": "3.9"}
        # Simulamos la excepción que lanza _get_moodle_token al fallar
        from fastapi import HTTPException

        mock_token.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Fallo de autenticación: Credenciales inválidas.",
        )

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "invalido", "password": "mal", "modalidad": "DISTANCIA"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "credenciales" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Servicio de Moodle no disponible (error de red)
# ---------------------------------------------------------------------------
def test_login_moodle_unavailable(client):
    """Si no se puede contactar a Moodle, debe retornar 503."""
    with (
        patch("app.core.config.Settings.get_moodle_config") as mock_cfg,
        patch("app.api.v1.endpoints.auth._get_moodle_token") as mock_token,
    ):
        mock_cfg.return_value = {"url": "http://fake.moodle.com", "token": "fake", "version": "3.9"}
        from fastapi import HTTPException

        mock_token.side_effect = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se puede conectar con el servicio de Moodle.",
        )

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "test", "password": "test", "modalidad": "DISTANCIA"},
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ---------------------------------------------------------------------------
# Usuario sin permisos administrativos
# ---------------------------------------------------------------------------
def test_login_insufficient_permissions(client):
    """Si el usuario no tiene los permisos necesarios, debe retornar 403."""
    with (
        patch("app.core.config.Settings.get_moodle_config") as mock_cfg,
        patch("app.api.v1.endpoints.auth._get_moodle_token") as mock_token,
        patch("app.api.v1.endpoints.auth._check_moodle_permissions") as mock_perm,
    ):
        mock_cfg.return_value = {"url": "http://fake.moodle.com", "token": "fake", "version": "3.9"}

        mock_token.return_value = "token_valido"
        from fastapi import HTTPException

        mock_perm.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no posee los permisos requeridos en Moodle.",
        )

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "invitado", "password": "invitado", "modalidad": "DISTANCIA"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "permisos" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# PRESENCIAL rechazado en login
# ---------------------------------------------------------------------------
def test_login_presencial_rejected(client, monkeypatch):
    """Login con modalidad PRESENCIAL debe ser rechazado con 403
    cuando ALLOW_PRESENCIAL es False (independiente del entorno)."""
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "ALLOW_PRESENCIAL", False)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "profesor", "password": "secreta", "modalidad": "PRESENCIAL"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "PRESENCIAL" in response.json()["detail"]
