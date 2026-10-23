from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricasSemestre(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    semestre: str = Field(alias="semester")
    total_ejecuciones: int = Field(alias="total_executions")
    total_cursos_creados: int = Field(alias="total_courses_created")
    total_usuarios_creados: int = Field(alias="total_users_created")
    total_matriculaciones: int = Field(alias="total_enrollments")
    total_errores: int = Field(alias="total_errors")
    duracion_promedio_segundos: float = Field(alias="avg_duration_seconds")
    ultima_completada: datetime | None = Field(default=None, alias="last_completed")


class EstadoSemaforo(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    semestre: str = Field(alias="semester")
    estado: str = Field(alias="status")  # green, yellow, red, gray
    tasa_error: float = Field(alias="error_rate")
    duracion_promedio: float = Field(alias="avg_duration")
    mensaje: str = Field(alias="message")


class EjecucionReciente(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    semestre: str = Field(alias="semester")
    nombre_archivo: str = Field(alias="filename")
    estado: str = Field(alias="status")
    iniciado_en: datetime | None = Field(default=None, alias="started_at")
    completado_en: datetime | None = Field(default=None, alias="completed_at")
    duracion_segundos: float | None = Field(default=None, alias="duration_seconds")
    metricas: dict[str, Any] | None = Field(default=None, alias="metrics")
    conteo_errores: int = Field(alias="errors_count")
    tasa_error: float = Field(alias="error_rate")
    semaforo: str = Field(alias="semaphore")
    version_moodle: str | None = Field(default=None, alias="moodle_version")
    modalidad: str | None = None
