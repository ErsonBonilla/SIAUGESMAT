"""
Esquemas Pydantic para la entidad Job (Execution) y sus errores.

Define los modelos de datos utilizados en las respuestas de los endpoints
de gestión de ejecuciones y errores.

Los nombres de campo internos son en español; los ``alias`` preservan el
contrato (wire format) en inglés que consume el frontend.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------
class ErrorSalida(BaseModel):
    """Representa un error registrado durante una ejecución."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    ejecucion_id: int = Field(alias="execution_id")
    tipo: str = Field(alias="type")
    identificador: str | None = Field(default=None, alias="identifier")
    mensaje: str | None = Field(default=None, alias="message")
    creado_en: datetime = Field(alias="created_at")

    # ---------------------------------------------------------------------------
    # Execution
    # ---------------------------------------------------------------------------


class EjecucionSalida(BaseModel):
    """Detalles completos de una ejecución, incluyendo métricas."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    nombre_archivo: str = Field(alias="filename")
    semestre: str = Field(alias="semester")
    modo: str = Field(alias="mode")
    estado: str = Field(alias="status")
    metricas: dict[str, object] | None = Field(default=None, alias="metrics")
    conteo_errores: int = Field(default=0, alias="errors_count")
    fase_actual: str | None = Field(default=None, alias="current_phase")
    porcentaje_progreso: float | None = Field(default=None, alias="progress_pct")
    progreso_actualizado_en: datetime | None = Field(default=None, alias="progress_updated_at")
    paso_actual: int | None = Field(default=None, alias="current_step")
    eta_segundos: float | None = Field(default=None, alias="eta_seconds")
    iniciado_en: datetime | None = Field(default=None, alias="started_at")
    completado_en: datetime | None = Field(default=None, alias="completed_at")
    duracion_segundos: float | None = Field(default=None, alias="duration_seconds")
    version_moodle: str | None = Field(default=None, alias="moodle_version")
    modalidad: str | None = Field(default=None, alias="modalidad")
    directorio_reporte: str | None = Field(default=None, alias="report_dir")
    id_tarea_celery: str | None = Field(default=None, alias="celery_task_id")
    creado_en: datetime = Field(alias="created_at")

    @model_validator(mode="after")
    def calcular_eta(self):
        if self.estado == "running" and self.porcentaje_progreso is not None and self.iniciado_en:
            pct = self.porcentaje_progreso
            elapsed = (datetime.now(UTC) - self.iniciado_en).total_seconds()
            if elapsed > 5 and pct > 0:
                rate = pct / elapsed
                if rate > 0:
                    eta = (100 - pct) / rate
                    self.eta_segundos = eta if eta < 86400 else None
        return self


class ListaEjecuciones(BaseModel):
    """Lista paginada de ejecuciones."""

    total: int
    items: list[EjecucionSalida]

    # ---------------------------------------------------------------------------
    # Procesamiento
    # ---------------------------------------------------------------------------


class RespuestaProceso(BaseModel):
    """Respuesta al encolar un proceso ETL."""

    execution_id: int
    job_id: str
    status: str
    message: str
