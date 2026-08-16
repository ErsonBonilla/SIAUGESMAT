"""
Configuración compartida para pruebas reales contra Moodle 3.9.

Genera un token JWT válido usando el SECRET del backend para
autenticar las llamadas a la API sin necesidad de login Moodle.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.seguridad import crear_token_acceso


def get_token(username: str = "admin", modalidad: str = "DISTANCIA") -> str:
    """Genera un token JWT firmado para pruebas."""
    return crear_token_acceso(
        {
            "sub": "1",
            "username": username,
            "modalidad": modalidad,
        }
    )
