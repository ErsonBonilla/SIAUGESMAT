"""
Punto de entrada de la API de SIAUGESMAT.

Crea y configura la aplicación FastAPI, incluye los enrutadores,
configura CORS y expone endpoints de health check.
"""

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.core.config import settings

# Configuración de logging estructurado (JSON en producción)
from app.core.configuracion_logging import configurar_logging
from app.db.sesion import inicializar_db

configurar_logging(debug=settings.DEBUG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """
    Maneja eventos de inicio y cierre de la aplicación.

    En startup se crean las tablas de la base de datos si no existen
    (útil para desarrollo; en producción se debe usar Alembic).
    """
    # Inicio
    logger.info(f"Iniciando {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    try:
        settings.validar_critico()
    except ValueError as e:
        logger.exception(f"Error de configuración: {e}")
        raise
    try:
        inicializar_db()
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.exception(f"Error al inicializar la base de datos: {e}")
        raise
    yield
    # Cierre
    logger.info("Apagando la aplicación...")

    # Crear la aplicación FastAPI


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Sistema de Integración y Automatización para la Gestión de Matrículas en Moodle",
    lifespan=ciclo_de_vida,
)

# Configurar CORS
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir el router principal de la API v1
app.include_router(v1_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Manejador global de errores no esperados
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def manejador_excepciones_global(request: Request, exc: Exception):
    """Convierte cualquier excepción no manejada en un 500 en español."""
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    logger.exception(f"Error no manejado en {request.method} {request.url}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Error interno del servidor. Intente nuevamente o contacte al administrador."
            )
        },
    )


@app.middleware("http")
async def proteccion_csrf(request: Request, call_next):
    """Protección CSRF (double-submit cookie) para métodos con efecto.

    Solo aplica a peticiones autenticadas por cookie: exige que la cabecera
    ``X-CSRF-Token`` coincida con la cookie ``csrf_token``. Se eximen:
    - login/logout (aún no hay cookie CSRF al iniciar sesión);
    - peticiones con ``Authorization: Bearer`` (no vulnerables a CSRF);
    - peticiones sin cookie ``auth_token`` (serán rechazadas 401 por la
      dependencia de autenticación, no por CSRF).
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        path = request.url.path.rstrip("/")
        if not (path.endswith("/auth/login") or path.endswith("/auth/logout")):
            auth = request.headers.get("authorization", "").lower()
            if not auth.startswith("bearer ") and request.cookies.get("auth_token"):
                cookie = request.cookies.get("csrf_token", "")
                header = request.headers.get("x-csrf-token", "")
                if not cookie or not secrets.compare_digest(cookie, header):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF inválido."},
                    )
    return await call_next(request)


@app.get("/", tags=["health"])
async def root():
    """Health check básico."""
    return {"status": "ok", "project": settings.PROJECT_NAME, "version": settings.PROJECT_VERSION}


@app.get("/health", tags=["health"])
async def verificar_salud():
    """Endpoint de verificación de estado."""
    return {"status": "healthy"}
