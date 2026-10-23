from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RespuestaSubidaCsv(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_lote: str = Field(alias="batch_id")
    tipo_entidad: str = Field(alias="entity_type")
    accion: str = Field(alias="action")
    total: int
    mensaje: str = Field(alias="message")


class ItemOperacionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    identificador: str = Field(alias="identifier")
    estado: str = Field(alias="status")
    mensaje_error: str | None = Field(default=None, alias="error_message")
    intento: int = Field(alias="attempt")


class RespuestaEstadoLote(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id_lote: str = Field(alias="batch_id")
    tipo_entidad: str = Field(alias="entity_type")
    accion: str = Field(alias="action")
    total: int
    pendientes: int = Field(alias="pending")
    procesando: int = Field(alias="processing")
    pausados: int = Field(default=0, alias="paused")
    completados: int = Field(alias="completed")
    fallidos: int = Field(alias="failed")
    cancelados: int = Field(default=0, alias="cancelled")
    modalidad: str | None = None
    creado_en: datetime | None = Field(default=None, alias="created_at")
    completado_en: datetime | None = Field(default=None, alias="completed_at")
    desplazamiento: int = Field(default=0, alias="offset")
    limite: int = Field(default=100, alias="limit")
    detalles: list[ItemOperacionSalida] = Field(alias="details")


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
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total: int
    items: list[LoteSalidaLista]


class MetricasMensualesOperacion(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    mes: str = Field(alias="month")
    usuarios_creados: int = Field(default=0, alias="users_created")
    usuarios_eliminados: int = Field(default=0, alias="users_deleted")
    categorias_creadas: int = Field(default=0, alias="categories_created")
    categorias_eliminadas: int = Field(default=0, alias="categories_deleted")
    cursos_eliminados: int = Field(default=0, alias="courses_deleted")
    total_errores: int = Field(default=0, alias="total_errors")


class RespuestaAnaliticaOperaciones(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    historial: list[MetricasMensualesOperacion] = Field(alias="history")


class RespuestaEliminarLotesAntiguos(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    lotes_eliminados: int = Field(alias="deleted_batches")
    mas_antiguos_que_dias: int = Field(alias="older_than_days")
