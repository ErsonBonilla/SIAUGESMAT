from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RespuestaSubidaCsv(BaseModel):
    batch_id: str
    entity_type: str
    action: str
    total: int
    message: str


class ItemOperacionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    identificador: str = Field(alias="identifier")
    estado: str = Field(alias="status")
    mensaje_error: str | None = Field(default=None, alias="error_message")
    intento: int = Field(alias="attempt")


class RespuestaEstadoLote(BaseModel):
    batch_id: str
    entity_type: str
    action: str
    total: int
    pending: int
    processing: int
    paused: int = 0
    completed: int
    failed: int
    cancelled: int = 0
    modalidad: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    offset: int = 0
    limit: int = 100
    details: list[ItemOperacionSalida]


class LoteSalidaLista(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_lote: str = Field(alias="batch_id")
    tipo_entidad: str = Field(alias="entity_type")
    accion: str = Field(alias="action")
    total: int = Field(alias="total")
    completados: int = Field(alias="completed")
    fallidos: int = Field(alias="failed")
    pausados: int = Field(default=0, alias="paused")
    modalidad: str = Field(alias="modalidad")
    creado_en: datetime = Field(alias="created_at")
    completado_en: datetime | None = Field(default=None, alias="completed_at")


class RespuestaListaLotes(BaseModel):
    total: int
    items: list[LoteSalidaLista]


class MetricasMensualesOperacion(BaseModel):
    month: str
    users_created: int = 0
    users_deleted: int = 0
    categories_created: int = 0
    categories_deleted: int = 0
    courses_deleted: int = 0
    total_errors: int = 0


class RespuestaAnaliticaOperaciones(BaseModel):
    history: list[MetricasMensualesOperacion]


class RespuestaEliminarLotesAntiguos(BaseModel):
    deleted_batches: int
    older_than_days: int
