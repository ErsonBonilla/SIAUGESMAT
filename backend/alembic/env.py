"""
Configuración del entorno de Alembic para SIAUGESMAT.

Lee la URL de la base de datos desde `app.core.config.settings` y utiliza
los metadatos de los modelos definidos en `app.db.base.Base`.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Asegurar que la raíz del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.base import Base

# Importar todos los modelos para que se registren en Base.metadata
# (no eliminar estos imports aunque parezcan no usados)
from app.db.models import ErrorLog, Execution  # noqa: F401

# Obtener la configuración de Alembic
config = context.config

# Sobrescribir la URL de la base de datos con la de la aplicación
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Configurar logging desde alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadatos compartidos de todos los modelos
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Ejecuta migraciones en modo offline (sin conexión a BD).

    Genera el SQL que se ejecutaría, útil para revisar cambios manualmente.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Ejecuta migraciones en modo online (con conexión real a la BD).
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()