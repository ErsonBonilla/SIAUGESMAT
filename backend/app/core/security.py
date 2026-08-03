"""
Seguridad y autenticación JWT para SIAUGESMAT.

Proporciona funciones para generar y validar tokens JWT locales
usados para proteger los endpoints de la aplicación.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt

from app.core.config import settings


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Crea un token JWT firmado con los datos suministrados.
    """
    if not settings.JWT_SECRET_KEY:
        raise ValueError(
            "JWT_SECRET_KEY no está configurada. "
            "Defínela en el archivo .env o como variable de entorno."
        )

    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + (expires_delta if expires_delta else timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodifica y valida un token JWT.

    Args:
        token: Token JWT a verificar.

    Returns:
        Diccionario con los claims del token.

    Raises:
        JWTError: Si el token es inválido, ha expirado o la firma no coincide.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
