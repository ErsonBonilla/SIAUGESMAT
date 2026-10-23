"""Modelos de respuesta para endpoints que antes devolvían dicts libres.

Replican exactamente la forma de las respuestas actuales para no romper
el contrato con el frontend; solo aportan tipado y documentación.
"""

from pydantic import BaseModel, ConfigDict, Field


# --- Queries (consulta asíncrona) ---
class RespuestaConsultaEncolada(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_tarea: str = Field(alias="task_id")
    entidad: str = Field(alias="entity")
    estado: str = Field(alias="status")
    mensaje: str = Field(alias="message")

    # --- Reports (ejecución ETL) ---


class InfoReporte(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    nombre: str = Field(alias="name")
    nombre_archivo: str = Field(alias="filename")
    tamano: int = Field(alias="size")


class RespuestaListaReportes(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ejecucion_id: int = Field(alias="execution_id")
    directorio_reporte: str = Field(alias="report_dir")
    reportes: list[InfoReporte] = Field(alias="reports")

    # --- Charts (analytics de ejecución) ---


class InfoGrafico(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    titulo: str = Field(alias="title")
    endpoint: str


class RespuestaListaGraficos(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ejecucion_id: int = Field(alias="execution_id")
    version_moodle: str | None = Field(default=None, alias="moodle_version")
    modalidad: str | None = None
    graficos: list[InfoGrafico] = Field(alias="charts")

    # --- Upload status ---


class EstadoSubidaEjecucion(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    estado: str = Field(alias="status")
    nombre_archivo: str = Field(alias="filename")


class EstadoSubidaLote(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_lote: str = Field(alias="batch_id")
    tipo_entidad: str = Field(alias="entity_type")
    accion: str = Field(alias="action")


class RespuestaEstadoSubida(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    permitido: bool = Field(alias="allowed")
    ejecucion: EstadoSubidaEjecucion | None = Field(default=None, alias="execution")
    lote: EstadoSubidaLote | None = Field(default=None, alias="batch")

    # --- Batch control (acciones sobre lotes) ---


class RespuestaAccionLote(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_lote: str = Field(alias="batch_id")
    mensaje: str = Field(alias="message")


class RespuestaPausaLote(RespuestaAccionLote):
    pausados: int = Field(alias="paused")


class RespuestaReanudacionLote(RespuestaAccionLote):
    reanudados: int = Field(alias="resumed")


class RespuestaCancelacionLote(RespuestaAccionLote):
    cancelados: int = Field(alias="cancelled")


class RespuestaListaReportesLote(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_lote: str = Field(alias="batch_id")
    reportes: list[dict] = Field(alias="reports")
