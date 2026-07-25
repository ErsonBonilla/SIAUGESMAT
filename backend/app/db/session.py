"""
Configuración de la sesión de base de datos para SIAUGESMAT.

Define el motor (engine) de SQLAlchemy conectado a PostgreSQL y la fábrica
de sesiones que se inyecta en los endpoints de FastAPI.
"""

import logging
from typing import Generator

from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Motor de base de datos (Parámetros comunes)
# ---------------------------------------------------------------------------
_is_sqlite = urlparse(settings.DATABASE_URL).scheme.startswith("sqlite")
engine_kwargs = {
    "pool_pre_ping": True,       # verifica que la conexión siga viva antes de usarla
    "echo": settings.DEBUG,      # imprime las consultas SQL solo en modo DEBUG
}

if not _is_sqlite:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_recycle"] = 3600

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# ---------------------------------------------------------------------------
# Fábrica de sesiones
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,             # las operaciones deben confirmarse explícitamente
    autoflush=False,              # no hace flush automático antes de cada consulta
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    Generador de sesiones de base de datos para FastAPI.

    Crea una nueva sesión por petición, la cierra al finalizar y realiza
    rollback en caso de error, evitando fugas de conexiones.

    Yields:
        Una sesión de SQLAlchemy lista para usar.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Crea tablas (solo desarrollo; migraciones vía Alembic en producción)."""
    if not settings.DEBUG:
        logger.info("Modo producción — no se crean tablas automáticamente, usar Alembic")
        return
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas exitosamente.")