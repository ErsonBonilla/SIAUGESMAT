"""Shim de compatibilidad: re-exporta action_handler de course_comparison desde el núcleo puro."""

from app.pipeline.course_comparison.action_handler import (
    handle_different_professor,
    handle_same_core_different_group,
    handle_same_professor,
)

__all__ = [
    "handle_different_professor",
    "handle_same_core_different_group",
    "handle_same_professor",
]
