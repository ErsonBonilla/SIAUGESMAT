"""
Punto de entrada de la API de SIAUGESMAT.

Crea y configura la aplicación FastAPI, incluye los enrutadores,
configura CORS y expone endpoints de health check.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.db.session import init_db

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Maneja eventos de inicio y cierre de la aplicación.

    En startup se crean las tablas de la base de datos si no existen
    (útil para desarrollo; en producción se debe usar Alembic).
    """
    # Inicio
    logger.info(f"Iniciando {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    try:
        settings.validate_critical()
    except ValueError as e:
        logger.error(f"Error de configuración: {e}")
        raise
    try:
        init_db()
        logger.info("Base de datos inicializada correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")
        raise
    yield
    # Cierre
    logger.info("Apagando la aplicación...")


# Crear la aplicación FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Sistema de Integración y Automatización para la Gestión de Matrículas en Moodle",
    lifespan=lifespan,
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
async def global_exception_handler(request: Request, exc: Exception):
    """Convierte cualquier excepción no manejada en un 500 en español."""
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    logger.exception(f"Error no manejado en {request.method} {request.url}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Error interno del servidor. "
                "Intente nuevamente o contacte al administrador."
            )
        },
    )


@app.get("/", tags=["health"])
async def root():
    """Health check básico."""
    return {"status": "ok", "project": settings.PROJECT_NAME, "version": settings.PROJECT_VERSION}


@app.get("/health", tags=["health"])
async def health_check():
    """Endpoint de verificación de estado."""
    return {"status": "healthy"}