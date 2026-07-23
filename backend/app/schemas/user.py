"""
Esquemas Pydantic para autenticación y usuarios.

Define los modelos de datos utilizados en los endpoints de autenticación
y en la dependencia de usuario actual.
"""

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Token JWT devuelto tras un inicio de sesión exitoso."""
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Credenciales enviadas por el usuario para iniciar sesión."""
    username: str
    password: str
    modalidad: str


class LoginResponse(TokenResponse):
    """Respuesta del login con información adicional del usuario."""
    user_id: int
    username: str
    modalidad: str


class UserInToken(BaseModel):
    """Datos del usuario extraídos del token JWT."""
    user_id: int
    username: str
    modalidad: str