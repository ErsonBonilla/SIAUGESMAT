"""
Endpoints de autenticación y perfil de usuario.

Proporciona:
- Inicio de sesión validando credenciales contra Moodle.
- Obtención del perfil del usuario autenticado (nombre real, foto, etc.).
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.schemas.user import TokenResponse, UserInToken
from app.services.moodle_errors import MoodleAPIError
from app.services.moodle_factory import get_moodle_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Modelos de solicitud y respuesta
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Credenciales de inicio de sesión."""
    username: str = Field(..., description="Nombre de usuario en Moodle")
    password: str = Field(..., min_length=1, description="Contraseña del usuario")
    modalidad: str = Field(..., description="Modalidad: PRESENCIAL o DISTANCIA")


class LoginResponse(BaseModel):
    """Respuesta exitosa con token de acceso."""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    modalidad: str


class UserProfileResponse(BaseModel):
    """Perfil público del usuario autenticado."""
    username: str
    firstname: str
    lastname: str
    profileimageurl: str  # URL de la imagen de perfil en Moodle


# ---------------------------------------------------------------------------
# Lógica de validación contra Moodle
# ---------------------------------------------------------------------------

async def _get_moodle_token(moodle_url: str, username: str, password: str) -> str:
    """
    Obtiene un token de autenticación de Moodle para el usuario dado.

    Llama al endpoint /login/token.php de la API de Moodle.

    Args:
        moodle_url: URL base de la instalación Moodle.
        username: Nombre de usuario en Moodle.
        password: Contraseña del usuario.

    Returns:
        Token de acceso de Moodle (string).

    Raises:
        HTTPException: Si las credenciales son inválidas o la API no responde.
    """
    token_url = f"{moodle_url.rstrip('/')}/login/token.php"
    payload = {
        "username": username,
        "password": password,
        "service": "FastAPI",
        "moodlewsrestformat": "json"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception(f"Error de red al contactar Moodle ({moodle_url}): {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se puede conectar con el servicio de Moodle."
            )

        try:
            data = response.json()
        except ValueError:
            logger.exception("Moodle no devolvió JSON válido en la autenticación")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Respuesta inesperada del servidor de Moodle."
            )

        token = data.get("token")
        if not token:
            error_msg = data.get("error", "Credenciales inválidas.")
            logger.warning(f"Autenticación fallida para {username}: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Fallo de autenticación: {error_msg}"
            )
        return token


async def _check_moodle_permissions(moodle_url: str, token: str) -> int:
    """
    Verifica que el token de Moodle tenga los privilegios necesarios.

    Para ello realiza una llamada de prueba a una función que requiere
    permisos administrativos (core_course_get_categories). Si la llamada
    es exitosa se considera que el usuario tiene acceso.

    Además, se obtiene el identificador numérico del usuario desde la
    respuesta de core_webservice_get_site_info.

    Args:
        moodle_url: URL base de la instalación Moodle.
        token: Token de autenticación de Moodle.

    Returns:
        userid (int) del usuario autenticado.

    Raises:
        HTTPException: Si la llamada de verificación falla por falta de permisos.
    """
    base_url = f"{moodle_url.rstrip('/')}/webservice/rest/server.php"
    common_params = {
        "wstoken": token,
        "moodlewsrestformat": "json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Obtener información del sitio y del usuario
        params = {**common_params, "wsfunction": "core_webservice_get_site_info"}
        try:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            site_info = resp.json()
        except httpx.HTTPError as exc:
            logger.exception(f"Error de red durante verificación de permisos: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo contactar a Moodle para verificar permisos."
            )
        except ValueError:
            logger.exception("Respuesta no JSON en verificación de permisos")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Respuesta inesperada de Moodle (verificación)."
            )

        if "error" in site_info:
            error_detail = site_info.get("error", "Error desconocido al obtener información.")
            logger.exception(f"Error en site_info: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No se pudo obtener información del usuario: {error_detail}"
            )

        userid = site_info.get("userid")
        if not userid:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo determinar el identificador del usuario."
            )

        # 2. Llamada de prueba a una función administrativa
        params["wsfunction"] = "core_course_get_categories"
        params["criteria[0][key]"] = "name"
        params["criteria[0][value]"] = ""  # Buscar cualquier categoría, solo para probar acceso
        try:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            categ_data = resp.json()
        except httpx.HTTPError as exc:
            logger.exception(f"Error durante llamada de prueba de permisos: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo verificar los permisos del usuario."
            )

        if "errorcode" in categ_data and categ_data["errorcode"] in (
            "accessexception", "requireloginerror", "nopermissions"
        ):
            error_msg = categ_data.get("message", "Permisos insuficientes.")
            logger.warning(f"Usuario {userid} no tiene permisos: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El usuario no posee los permisos requeridos en Moodle."
            )

        logger.info(f"Usuario {userid} validado con permisos adecuados.")
        return userid


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse, summary="Iniciar sesión")
async def login(request: LoginRequest, response: Response):
    """
    Autentica al usuario contra Moodle y devuelve un token JWT propio.

    Raises:
        HTTPException 401: Credenciales inválidas.
        HTTPException 403: El usuario no tiene los permisos necesarios.
        HTTPException 502/503: Error de comunicación con Moodle.
    """
    # 1. Validar modalidad PRESENCIAL bloqueada
    if request.modalidad.upper() == "PRESENCIAL" and not settings.ALLOW_PRESENCIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Modalidad PRESENCIAL no disponible actualmente."
        )

    # 2. Resolver Moodle según la modalidad
    moodle_config = settings.get_moodle_config(request.modalidad)
    moodle_url = moodle_config["url"]

    # 3. Obtener token de Moodle
    moodle_token = await _get_moodle_token(moodle_url, request.username, request.password)

    # 4. Verificar permisos y obtener userid
    user_id = await _check_moodle_permissions(moodle_url, moodle_token)

    # 5. Generar token JWT local (con modalidad)
    access_token = create_access_token(
        data={
            "sub": str(user_id),
            "username": request.username,
            "modalidad": request.modalidad,
        }
    )

    logger.info(
        f"Inicio de sesión exitoso para {request.username} "
        f"(userid={user_id}, modalidad={request.modalidad})"
    )

    # Cookie HttpOnly+Secure para que el SSR del frontend autorice rutas
    # protegidas. La misma expiración que el JWT (JWT_EXPIRE_MINUTES).
    response.set_cookie(
        key="auth_token",
        value=access_token,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax",
    )

    return LoginResponse(
        access_token=access_token,
        user_id=user_id,
        username=request.username,
        modalidad=request.modalidad,
    )


@router.post("/logout", summary="Cerrar sesión")
async def logout(response: Response):
    """Elimina la cookie de sesión (HttpOnly) del navegador."""
    response.delete_cookie("auth_token", path="/")
    return {"status": "ok"}


@router.get("/me", response_model=UserProfileResponse, summary="Obtener perfil del usuario autenticado")
async def get_my_profile(current_user: UserInToken = Depends(get_current_user)):
    """
    Devuelve el primer nombre, apellido y la URL de la imagen de perfil
    del usuario autenticado, obtenidos desde Moodle.

    Requiere el token JWT en la cabecera Authorization.
    """
    moodle = get_moodle_service(current_user.modalidad)
    try:
        # Buscar el usuario en Moodle por su username (el que viene en el JWT)
        users = await moodle.get_users("username", [current_user.username])
        if not users:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en Moodle")

        user = users[0]
        return UserProfileResponse(
            username=current_user.username,
            firstname=user.get("firstname") or current_user.username,
            lastname=user.get("lastname") or "",
            profileimageurl=user.get("profileimageurl") or "",
        )
    except MoodleAPIError as e:
        logger.exception(f"Error al obtener perfil de {current_user.username}: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="No se pudo obtener el perfil del usuario")
    except Exception as e:
        logger.exception("Error inesperado al obtener perfil")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno")
    finally:
        await moodle.close()