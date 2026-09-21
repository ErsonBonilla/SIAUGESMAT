"""
Pruebas de autenticación por cookie y protección CSRF (double-submit).

Cubre la migración de H3: el JWT viaja en la cookie HttpOnly ``auth_token``
y las mutaciones autenticadas por cookie exigen la cabecera ``X-CSRF-Token``
coincidente con la cookie ``csrf_token``.
"""

from fastapi import status

from app.core.seguridad import crear_token_acceso

TOKEN_AUTH = crear_token_acceso(data={"sub": "1", "username": "testuser", "modalidad": "DISTANCIA"})


def _cookies_auth(csrf: str | None = None) -> dict[str, str]:
    cookies = {"auth_token": TOKEN_AUTH}
    if csrf is not None:
        cookies["csrf_token"] = csrf
    return cookies


# ---------------------------------------------------------------------------
# Autenticación por cookie
# ---------------------------------------------------------------------------


def test_auth_por_cookie_valida(client):
    """Un JWT válido en la cookie auth_token autentica la petición."""
    response = client.get(
        "/api/v1/upload/status",
        cookies={"auth_token": TOKEN_AUTH},
    )
    assert response.status_code == status.HTTP_200_OK


def test_auth_por_bearer_sigue_funcionando(client, encabezados_auth):
    """El fallback por cabecera Authorization: Bearer sigue vigente."""
    response = client.get("/api/v1/upload/status", headers=encabezados_auth)
    assert response.status_code == status.HTTP_200_OK


def test_auth_sin_credenciales_401(client):
    """Sin cookie ni Bearer la petición debe rechazarse con 401."""
    response = client.get("/api/v1/upload/status")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# CSRF (double-submit cookie)
# ---------------------------------------------------------------------------

MUTACION = "/api/v1/jobs/1/process"


def test_csrf_ok(client):
    """Cookie CSRF y cabecera coincidentes: la mutación pasa el chequeo."""
    response = client.post(
        MUTACION,
        cookies=_cookies_auth(csrf="tokencsrf"),
        headers={"X-CSRF-Token": "tokencsrf"},
    )
    # 404 = el middleware CSRF dejó pasar y el endpoint no encontró la ejecución.
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_csrf_header_distinto_403(client):
    """Cabecera que no coincide con la cookie → 403."""
    response = client.post(
        MUTACION,
        cookies=_cookies_auth(csrf="tokencsrf"),
        headers={"X-CSRF-Token": "otrovalor"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_csrf_sin_cookie_403(client):
    """Sin cookie CSRF (pero sí auth) → 403."""
    response = client.post(
        MUTACION,
        cookies=_cookies_auth(csrf=None),
        headers={"X-CSRF-Token": "tokencsrf"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_csrf_bearer_exento(client, encabezados_auth):
    """Con Authorization: Bearer no se valida CSRF."""
    response = client.post(MUTACION, headers=encabezados_auth)
    # 404 = CSRF no aplicó (Bearer) y el endpoint no encontró la ejecución.
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_login_exento_de_csrf(client):
    """El endpoint de login está exento del chequeo CSRF."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "u", "password": "p", "modalidad": "PRESENCIAL"},
    )
    # 403 por modalidad bloqueada (no por CSRF).
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "PRESENCIAL" in response.json()["detail"]
