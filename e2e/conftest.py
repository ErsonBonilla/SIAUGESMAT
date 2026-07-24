"""
Configuración compartida para pruebas reales contra Moodle 3.9.

Genera un token JWT válido usando el SECRET del backend para
autenticar las llamadas a la API sin necesidad de login Moodle.
"""

import sys
from pathlib import Path

# Agregar backend al PYTHONPATH para importar app.core.security
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

from app.core.security import create_access_token


def get_token(username: str = "admin", modalidad: str = "DISTANCIA") -> str:
    """Genera un token JWT firmado para pruebas."""
    return create_access_token({
        "sub": "1",
        "username": username,
        "modalidad": modalidad,
    })
