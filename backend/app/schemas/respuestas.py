"""Modelos de respuesta para endpoints que antes devolvían dicts libres.

Replican exactamente la forma de las respuestas actuales para no romper
el contrato con el frontend; solo aportan tipado y documentación.
"""

from pydantic import BaseModel


# --- Queries (consulta asíncrona) ---
class RespuestaConsultaEncolada(BaseModel):
    task_id: str
    entity: str
    status: str
    message: str

    # --- Reports (ejecución ETL) ---


class InfoReporte(BaseModel):
    name: str
    filename: str
    size: int


class RespuestaListaReportes(BaseModel):
    execution_id: int
    report_dir: str
    reports: list[InfoReporte]

    # --- Charts (analytics de ejecución) ---


class InfoGrafico(BaseModel):
    id: str
    title: str
    endpoint: str


class RespuestaListaGraficos(BaseModel):
    execution_id: int
    moodle_version: str | None = None
    modalidad: str | None = None
    charts: list[InfoGrafico]

    # --- Upload status ---


class EstadoSubidaEjecucion(BaseModel):
    id: int
    status: str
    filename: str


class EstadoSubidaLote(BaseModel):
    batch_id: str
    entity_type: str
    action: str


class RespuestaEstadoSubida(BaseModel):
    allowed: bool
    execution: EstadoSubidaEjecucion | None = None
    batch: EstadoSubidaLote | None = None

    # --- Batch control (acciones sobre lotes) ---


class RespuestaAccionLote(BaseModel):
    batch_id: str
    message: str


class RespuestaPausaLote(RespuestaAccionLote):
    paused: int


class RespuestaReanudacionLote(RespuestaAccionLote):
    resumed: int


class RespuestaCancelacionLote(RespuestaAccionLote):
    cancelled: int


class RespuestaListaReportesLote(BaseModel):
    batch_id: str
    reports: list[dict]
