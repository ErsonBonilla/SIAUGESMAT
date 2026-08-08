"""Shim de compatibilidad: re-exporta el parsing de shortnames desde el núcleo puro.

La implementación vive en app.pipeline.shortnames. Este módulo se mantiene
como puente para workers, tests y servicios existentes.
"""

from app.pipeline.shortnames import (
    SHORTNAME_PATTERN,
    SIAUGESMAT_PATTERN,
    parse_shortname,
)

__all__ = ["SHORTNAME_PATTERN", "SIAUGESMAT_PATTERN", "parse_shortname"]
