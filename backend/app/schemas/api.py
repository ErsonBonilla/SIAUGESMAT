"""Modelos de respuesta para endpoints que antes devolvían dicts libres.

Replican exactamente la forma de las respuestas actuales para no romper
el contrato con el frontend; solo aportan tipado y documentación.
"""

from pydantic import BaseModel


# --- Queries (consulta asíncrona) ---
class QueryEnqueuedResponse(BaseModel):
    task_id: str
    entity: str
    status: str
    message: str


# --- Reports (ejecución ETL) ---
class ReportInfo(BaseModel):
    name: str
    filename: str
    size: int


class ReportsListResponse(BaseModel):
    execution_id: int
    report_dir: str
    reports: list[ReportInfo]


# --- Charts (analytics de ejecución) ---
class ChartInfo(BaseModel):
    id: str
    title: str
    endpoint: str


class ChartsListResponse(BaseModel):
    execution_id: int
    moodle_version: str | None = None
    modalidad: str | None = None
    charts: list[ChartInfo]


# --- Upload status ---
class UploadStatusExecution(BaseModel):
    id: int
    status: str
    filename: str


class UploadStatusBatch(BaseModel):
    batch_id: str
    entity_type: str
    action: str


class UploadStatusResponse(BaseModel):
    allowed: bool
    execution: UploadStatusExecution | None = None
    batch: UploadStatusBatch | None = None


# --- Batch control (acciones sobre lotes) ---
class BatchActionResponse(BaseModel):
    batch_id: str
    message: str


class BatchPauseResponse(BatchActionResponse):
    paused: int


class BatchResumeResponse(BatchActionResponse):
    resumed: int


class BatchCancelResponse(BatchActionResponse):
    cancelled: int


class BatchReportsListResponse(BaseModel):
    batch_id: str
    reports: list[dict]
