"""
Esquemas Pydantic para la entidad Job (Execution) y sus errores.

Define los modelos de datos utilizados en las respuestas de los endpoints
de gestión de ejecuciones y errores.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, model_validator


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------
class ErrorOut(BaseModel):
    """Representa un error registrado durante una ejecución."""
    id: int
    execution_id: int
    type: str
    identifier: str | None = None
    message: str | None = None
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
    metrics: dict[str, int] | None = None
    errors_count: int = 0
    current_phase: str | None = None
    progress_pct: float | None = None
    progress_updated_at: datetime | None = None
    current_step: int | None = None
    eta_seconds: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    moodle_version: str | None = None
    modalidad: str | None = None
    report_dir: str | None = None
    celery_task_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_eta(self):
        if self.status == "running" and self.progress_pct is not None and self.started_at:
            pct = self.progress_pct
            elapsed = (datetime.now(UTC) - self.started_at).total_seconds()
            if elapsed > 5 and pct > 0:
                rate = pct / elapsed
                if rate > 0:
                    eta = (100 - pct) / rate
                    self.eta_seconds = eta if eta < 86400 else None
        return self


class ExecutionList(BaseModel):
    """Lista paginada de ejecuciones."""
    total: int
    items: list[ExecutionOut]


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------
class ProcessResponse(BaseModel):
    """Respuesta al encolar un proceso ETL."""
    execution_id: int
    job_id: str
    status: str
    message: str
