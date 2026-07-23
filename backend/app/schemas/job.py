"""
Esquemas Pydantic para la entidad Job (Execution) y sus errores.

Define los modelos de datos utilizados en las respuestas de los endpoints
de gestión de ejecuciones y errores.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------
class ErrorOut(BaseModel):
    """Representa un error registrado durante una ejecución."""
    id: int
    execution_id: int
    type: str
    identifier: Optional[str] = None
    message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
class ExecutionOut(BaseModel):
    """Detalles completos de una ejecución, incluyendo métricas."""
    id: int
    filename: str
    semester: str
    mode: str
    status: str
    metrics: Optional[Dict[str, Any]] = None
    errors_count: int = 0
    current_phase: Optional[str] = None
    progress_pct: Optional[float] = None
    current_step: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    moodle_version: Optional[str] = None
    modalidad: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExecutionList(BaseModel):
    """Lista paginada de ejecuciones."""
    total: int
    items: List[ExecutionOut]


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------
class ProcessResponse(BaseModel):
    """Respuesta al encolar un proceso ETL."""
    execution_id: int
    job_id: str
    status: str
    message: str