"""
Endpoints de autenticación y perfil de usuario.

Proporciona:
- Inicio de sesión validando credenciales contra Moodle.
- Obtención del perfil del usuario autenticado (nombre real, foto, etc.).
"""

import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import settings
from app.core.dependencies import obtener_limitador_login, obtener_usuario_actual
from app.core.limitador_login import LimitadorLogin
from app.core.seguridad import crear_token_acceso
from app.schemas.usuario import (
    RespuestaLogin,
    RespuestaPerfilUsuario,
    SolicitudLogin,
    UsuarioEnToken,
)
from app.services.errores_moodle import ErrorApiMoodle
from app.services.fabrica_moodle import obtener_servicio_moodle

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Lógica de validación contra Moodle
# ---------------------------------------------------------------------------


async def _obtener_token_moodle(moodle_url: str, username: str, password: str) -> str:
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
        "moodlewsrestformat": "json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception(f"Error de red al contactar Moodle ({moodle_url}): {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se puede conectar con el servicio de Moodle.",
            ) from exc

        try:
            data = response.json()
        except ValueError:
            logger.exception("Moodle no devolvió JSON válido en la autenticación")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Respuesta inesperada del servidor de Moodle.",
            ) from None

        token = data.get("token")
        if not token:
            error_msg = data.get("error", "Credenciales inválidas.")
            logger.warning(f"Autenticación fallida para {username}: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Fallo de autenticación: {error_msg}",
            )
        return token


async def _verificar_permisos_moodle(moodle_url: str, token: str) -> int:
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
            resp = await client.post(base_url, data=params)
            resp.raise_for_status()
            site_info = resp.json()
        except httpx.HTTPError as exc:
            logger.exception(f"Error de red durante verificación de permisos: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo contactar a Moodle para verificar permisos.",
            ) from exc
        except ValueError:
            logger.exception("Respuesta no JSON en verificación de permisos")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Respuesta inesperada de Moodle (verificación).",
            ) from None

        if "error" in site_info:
            error_detail = site_info.get("error", "Error desconocido al obtener información.")
            logger.exception(f"Error en site_info: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No se pudo obtener información del usuario: {error_detail}",
            )

        userid = site_info.get("userid")
        if not userid:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo determinar el identificador del usuario.",
            )

            # 2. Llamada de prueba a una función administrativa
        params["wsfunction"] = "core_course_get_categories"
        params["criteria[0][key]"] = "name"
        params["criteria[0][value]"] = ""  # Buscar cualquier categoría, solo para probar acceso
        try:
            resp = await client.post(base_url, data=params)
            resp.raise_for_status()
            categ_data = resp.json()
        except httpx.HTTPError as exc:
            logger.exception(f"Error durante llamada de prueba de permisos: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo verificar los permisos del usuario.",
            ) from exc

        if "errorcode" in categ_data and categ_data["errorcode"] in (
            "accessexception",
            "requireloginerror",
            "nopermissions",
        ):
            error_msg = categ_data.get("message", "Permisos insuficientes.")
            logger.warning(f"Usuario {userid} no tiene permisos: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El usuario no posee los permisos requeridos en Moodle.",
            )

        logger.info(f"Usuario {userid} validado con permisos adecuados.")
        return userid

        # ---------------------------------------------------------------------------
        # Endpoints
        # ---------------------------------------------------------------------------


@router.post("/login", response_model=RespuestaLogin, summary="Iniciar sesión")
async def iniciar_sesion(
    request: SolicitudLogin,
    response: Response,
    req: Request,
    limitador: LimitadorLogin = Depends(obtener_limitador_login),
):
    """
    Autentica al usuario contra Moodle y devuelve un token JWT propio.

    Raises:
        HTTPException 401: Credenciales inválidas.
        HTTPException 403: El usuario no tiene los permisos necesarios.
        HTTPException 429: Demasiados intentos fallidos (rate limit).
        HTTPException 502/503: Error de comunicación con Moodle.
    """
    # 0. Rate limiting por IP + usuario (protección contra fuerza bruta)
    ip = req.client.host if req.client else "desconocida"
    if await limitador.esta_bloqueado(ip, request.nombre_usuario):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intente nuevamente en unos minutos.",
        )

    # 1. Validar modalidad PRESENCIAL bloqueada
    if request.modalidad.upper() == "PRESENCIAL" and not settings.ALLOW_PRESENCIAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Modalidad PRESENCIAL no disponible actualmente.",
        )

        # 2. Resolver Moodle según la modalidad
    moodle_config = settings.obtener_config_moodle(request.modalidad)
    moodle_url = moodle_config["url"]

    # 3. Obtener token de Moodle
    moodle_token = await _obtener_token_moodle(
        moodle_url, request.nombre_usuario, request.contrasena
    )

    # 4. Verificar permisos y obtener userid
    user_id = await _verificar_permisos_moodle(moodle_url, moodle_token)

    # 5. Generar token JWT local (con modalidad)
    access_token = crear_token_acceso(
        data={
            "sub": str(user_id),
            "username": request.nombre_usuario,
            "modalidad": request.modalidad,
        }
    )

    # 6. Limpiar el contador de intentos fallidos del usuario
    await limitador.registrar_exito(ip, request.nombre_usuario)

    logger.info(
        f"Inicio de sesión exitoso para {request.nombre_usuario} "
        f"(userid={user_id}, modalidad={request.modalidad})"
    )

    es_https = (
        req.url.scheme == "https" or req.headers.get("x-forwarded-proto", "").lower() == "https"
    )

    # Cookie HttpOnly para que el SSR del frontend y la API autoricen rutas
    # protegidas. La misma expiración que el JWT (JWT_EXPIRE_MINUTES).
    # `secure` se activa bajo HTTPS (p. ej. tras Nginx) y se desactiva en HTTP local.
    response.set_cookie(
        key="auth_token",
        value=access_token,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
        httponly=True,
        secure=es_https,
        samesite="lax",
    )

    # Cookie CSRF (no-HttpOnly) para el esquema double-submit: el frontend la
    # lee y la devuelve en la cabecera X-CSRF-Token en cada mutación.
    response.set_cookie(
        key="csrf_token",
        value=secrets.token_urlsafe(32),
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
        httponly=False,
        secure=es_https,
        samesite="lax",
    )

    return RespuestaLogin(
        token_acceso=access_token,
        usuario_id=user_id,
        nombre_usuario=request.nombre_usuario,
        modalidad=request.modalidad,
    )


@router.post("/logout", summary="Cerrar sesión")
async def cerrar_sesion(response: Response):
    """Elimina las cookies de sesión y CSRF del navegador."""
    response.delete_cookie("auth_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    return {"status": "ok"}


@router.get(
    "/me", response_model=RespuestaPerfilUsuario, summary="Obtener perfil del usuario autenticado"
)
async def obtener_mi_perfil(usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual)):
    """
    Devuelve el primer nombre, apellido y la URL de la imagen de perfil
    del usuario autenticado, obtenidos desde Moodle.

    Requiere el token JWT en la cabecera Authorization.
    """
    moodle = obtener_servicio_moodle(usuario_actual.modalidad)
    try:
        # Buscar el usuario en Moodle por su username (el que viene en el JWT)
        users = await moodle.obtener_usuarios("username", [usuario_actual.username])
        if not users:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en Moodle"
            )

        user = users[0]
        return RespuestaPerfilUsuario(
            username=usuario_actual.username,
            firstname=user.get("firstname") or usuario_actual.username,
            lastname=user.get("lastname") or "",
            profileimageurl=user.get("profileimageurl") or "",
        )
    except ErrorApiMoodle as e:
        logger.exception(f"Error al obtener perfil de {usuario_actual.username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo obtener el perfil del usuario",
        ) from e
    except Exception:
        logger.exception("Error inesperado al obtener perfil")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno"
        ) from None
    finally:
        await moodle.cerrar()
