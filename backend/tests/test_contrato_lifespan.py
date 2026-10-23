"""
Garantiza que el lifespan de FastAPI esté registrado (regresión de D1).

Si alguien vuelve a renombrar el kwarg `lifespan=` a español, el constructor
de FastAPI se traga el kwarg en `extra` y el arranque (inicializar_db +
validar_critico) deja de ejecutarse en silencio.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_lifespan_registrado():
    assert type(app.router.lifespan_context).__name__ != "_DefaultLifespan"


def test_startup_ejecuta_inicializar_db():
    """El arranque debe llamar a inicializar_db() (regresión de D1)."""
    with patch("app.main.inicializar_db") as mock_inicializar, TestClient(app):
        mock_inicializar.assert_called_once()
