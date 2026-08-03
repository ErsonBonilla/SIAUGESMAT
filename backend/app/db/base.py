"""
Base declarativa de SQLAlchemy para los modelos de SIAUGESMAT.

Todos los modelos de base de datos deben heredar de `Base` para ser
registrados en la metadata compartida.
"""

from sqlalchemy.orm import DeclarativeMeta, declarative_base

Base: DeclarativeMeta = declarative_base()
