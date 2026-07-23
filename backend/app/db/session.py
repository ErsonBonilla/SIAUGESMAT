"""
Configuración de la sesión de base de datos para SIAUGESMAT.

Define el motor (engine) de SQLAlchemy conectado a PostgreSQL y la fábrica
de sesiones que se inyecta en los endpoints de FastAPI.
"""

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Motor de base de datos (Parámetros comunes)
# ---------------------------------------------------------------------------
engine_kwargs = {
    "pool_pre_ping": True,       # verifica que la conexión siga viva antes de usarla
    "echo": settings.DEBUG,      # imprime las consultas SQL solo en modo DEBUG
}

# Solo se agregan pool_size / max_overflow si el motor los soporta (PostgreSQL, MySQL, etc.)
# SQLite no los acepta y lanzaría un error.
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs["pool_size"] = 10       # número de conexiones permanentes en el pool
    engine_kwargs["max_overflow"] = 20    # conexiones adicionales temporales si el pool se llena

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
    """
    Crea todas las tablas definidas en los modelos que heredan de Base.

    Útil para entornos de desarrollo o pruebas. En producción se recomienda
    usar Alembic para gestionar las migraciones.
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas exitosamente.")