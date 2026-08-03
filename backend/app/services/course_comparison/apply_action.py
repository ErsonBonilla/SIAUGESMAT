"""Shim de compatibilidad: re-exporta apply_action de course_comparison desde el núcleo puro."""
from app.pipeline.course_comparison.apply_action import apply_action

__all__ = ["apply_action"]
