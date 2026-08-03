"""
Dependencias inyectables para los endpoints de SIAUGESMAT.

Centraliza:
- La sesión de base de datos (importada de app.db.session).
- La validación del usuario actual mediante JWT.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_access_token
from app.db.session import get_db as get_db
from app.schemas.user import UserInToken

# Esquema de autenticación HTTP Bearer para Swagger y dependencias
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserInToken:
    """
    Valida el token JWT de la cabecera Authorization y devuelve los
    datos del usuario autenticado.

    Args:
        credentials: Credenciales extraídas del header Authorization.

    Returns:
        UserInToken con los campos user_id y username.

    Raises:
        HTTPException 401: Token inválido, expirado o con datos insuficientes.
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
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
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: ID de usuario no numérico.",
        )

    return UserInToken(user_id=user_id_int, username=username, modalidad=modalidad)