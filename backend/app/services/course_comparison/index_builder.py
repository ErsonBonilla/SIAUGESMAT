"""Shim de compatibilidad: re-exporta index_builder de course_comparison desde el núcleo puro."""
from app.pipeline.course_comparison.index_builder import (
    build_base_key_index,
    build_core_index,
    build_shortname_index,
)

__all__ = ["build_shortname_index", "build_base_key_index", "build_core_index"]
