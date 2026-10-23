"""
Esquemas Pydantic para autenticación y usuarios.

Define los modelos de datos utilizados en los endpoints de autenticación
y en la dependencia de usuario actual.
"""

from pydantic import BaseModel, ConfigDict, Field


class RespuestaToken(BaseModel):
    """Token JWT devuelto tras un inicio de sesión exitoso."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    token_acceso: str = Field(alias="access_token")
    tipo_token: str = Field(default="bearer", alias="token_type")


class SolicitudLogin(BaseModel):
    """Credenciales enviadas por el usuario para iniciar sesión."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    nombre_usuario: str = Field(alias="username", description="Nombre de usuario en Moodle")
    contrasena: str = Field(alias="password", min_length=1, description="Contraseña del usuario")
    modalidad: str = Field(description="Modalidad: PRESENCIAL o DISTANCIA")


class RespuestaLogin(RespuestaToken):
    """Respuesta del login con información adicional del usuario."""

    usuario_id: int = Field(alias="user_id")
    nombre_usuario: str = Field(alias="username")
    modalidad: str


class RespuestaPerfilUsuario(BaseModel):
    """Perfil público del usuario autenticado."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    nombre_usuario: str = Field(alias="username")
    nombres: str = Field(alias="firstname")
    apellidos: str = Field(alias="lastname")
    url_imagen_perfil: str = Field(alias="profileimageurl")


class UsuarioEnToken(BaseModel):
    """Datos del usuario extraídos del token JWT."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    usuario_id: int = Field(alias="user_id")
    nombre_usuario: str = Field(alias="username")
    modalidad: str

    @property
    def user_id(self) -> int:
        return self.usuario_id

    @property
    def username(self) -> str:
        return self.nombre_usuario
