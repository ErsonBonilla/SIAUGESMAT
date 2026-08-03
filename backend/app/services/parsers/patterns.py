"""Shim de compatibilidad: re-exporta el parsing de shortnames desde el núcleo puro.

La implementación vive en app.pipeline.shortnames. Este módulo se mantiene
como puente para workers, tests y servicios existentes.
"""
from app.pipeline.shortnames import (
    SIAUGESMAT_PATTERN,
    SHORTNAME_PATTERN,
    parse_shortname,
)

__all__ = ["SIAUGESMAT_PATTERN", "SHORTNAME_PATTERN", "parse_shortname"]
