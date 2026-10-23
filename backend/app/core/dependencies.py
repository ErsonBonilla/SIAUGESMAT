"""
Dependencias inyectables para los endpoints de SIAUGESMAT.

Centraliza:
- La sesión de base de datos (importada de app.db.sesion).
- La validación del usuario actual mediante JWT.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.seguridad import decodificar_token_acceso
from app.db.sesion import obtener_db as obtener_db
from app.schemas.usuario import UsuarioEnToken

__all__ = ["obtener_db", "obtener_limitador_login", "obtener_usuario_actual"]

# Esquema de autenticación HTTP Bearer para Swagger y dependencias.
# auto_error=False: la cookie HttpOnly `auth_token` es la vía principal de
# autenticación; el Bearer se acepta como fallback (e2e, CLI) sin forzar error.
bearer_scheme = HTTPBearer(auto_error=False)


async def obtener_usuario_actual(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UsuarioEnToken:
    """
    Valida el JWT de la cookie HttpOnly ``auth_token`` (o, como fallback,
    de la cabecera ``Authorization: Bearer``) y devuelve los datos del
    usuario autenticado.

    Args:
        request: Petición HTTP (para leer la cookie).
        credentials: Credenciales Bearer opcionales (fallback).

    Returns:
        UserInToken con los campos user_id, username y modalidad.

    Raises:
        HTTPException 401: Sin credenciales, o token inválido/expirado.
    """
    token = request.cookies.get("auth_token") or (credentials.credentials if credentials else None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado.",
        )
    try:
        payload = decodificar_token_acceso(token)
        user_id = payload.get("sub")
        username = payload.get("username")
        modalidad = payload.get("modalidad")

        if user_id is None or username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: datos insuficientes.",
            )

        if not modalidad:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: modalidad no especificada. Inicie sesión nuevamente.",
            )

            # El ID de usuario se guardó como string en el JWT; lo convertimos.
        user_id_int = int(user_id)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        ) from None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: ID de usuario no numérico.",
        ) from None

    return UsuarioEnToken(user_id=user_id_int, username=username, modalidad=modalidad)


async def obtener_limitador_login():
    """Provee el limitador de intentos de login (Redis, fail-open).

    Se expone como dependencia para poder sobreescribirlo en tests con una
    implementación falsa que no requiera Redis.
    """
    from app.core.limitador_login import LimitadorLogin

    return LimitadorLogin()
