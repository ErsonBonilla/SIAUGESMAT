"""
Modelos de base de datos (SQLAlchemy ORM) para SIAUGESMAT.

Define las tablas `ejecuciones`, `registros_error`, `registros_ejecucion`,
`lotes_operacion`, `items_operacion` y `resultados_consulta` utilizadas
para el seguimiento de los procesos ETL, las operaciones masivas y las
consultas asíncronas.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Ejecucion(Base):
    """
    Representa una ejecución del proceso ETL a partir de un archivo Excel.

    Almacena el estado, el semestre, el modo (courses/users/both), las
    métricas finales y los tiempos de inicio y fin.
    """

    __tablename__ = "ejecuciones"

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String(500), nullable=False)
    semestre = Column(String(10), nullable=False, index=True)
    modo = Column(String(20), nullable=False, default="both")
    estado = Column(String(20), nullable=False, default="pending", index=True)
    metricas = Column(JSON, nullable=True)
    conteo_errores = Column(Integer, default=0)
    directorio_reporte = Column(String(500), nullable=True)
    iniciado_en = Column(DateTime(timezone=True), nullable=True)
    completado_en = Column(DateTime(timezone=True), nullable=True)
    duracion_segundos = Column(Float, nullable=True)
    fase_actual = Column(String(100), nullable=True)
    porcentaje_progreso = Column(Float, nullable=True)
    progreso_actualizado_en = Column(DateTime(timezone=True), nullable=True)
    paso_actual = Column(Integer, nullable=True)
    version_moodle = Column(String(10), nullable=True)
    modalidad = Column(String(20), nullable=True, index=True)
    checkpoint_fase = Column(JSON, nullable=True)
    id_tarea_celery = Column(String(255), nullable=True, index=True)
    creado_en = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )

    errores = relationship(
        "RegistroError", back_populates="ejecucion", cascade="all, delete-orphan"
    )
    registros = relationship(
        "RegistroEjecucion", back_populates="ejecucion", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Ejecucion id={self.id} nombre={self.nombre_archivo!r} estado={self.estado!r}>"


class RegistroError(Base):
    __tablename__ = "registros_error"

    id = Column(Integer, primary_key=True, index=True)
    ejecucion_id = Column(Integer, ForeignKey("ejecuciones.id"), nullable=False, index=True)
    tipo = Column(String(50), nullable=False)
    identificador = Column(String(255), nullable=True)
    mensaje = Column(Text, nullable=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    ejecucion = relationship("Ejecucion", back_populates="errores")

    def __repr__(self) -> str:
        return f"<RegistroError id={self.id} ejecucion_id={self.ejecucion_id} tipo={self.tipo!r}>"


class RegistroEjecucion(Base):
    """
    Registro detallado de acciones e incidencias durante una ejecución ETL.

    Almacena cada operación (creación, eliminación, activación, error, alerta)
    con datos estructurados para la generación de reportes.
    """

    __tablename__ = "registros_ejecucion"

    id = Column(Integer, primary_key=True, index=True)
    ejecucion_id = Column(Integer, ForeignKey("ejecuciones.id"), nullable=False, index=True)
    fase = Column(String(10), nullable=False)  # valores: "1","2","3","4","critical"
    accion = Column(String(50), nullable=False)
    identificador = Column(String(255), nullable=True)
    detalle = Column(JSON, nullable=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    ejecucion = relationship("Ejecucion", back_populates="registros")

    def __repr__(self) -> str:
        return (
            f"<RegistroEjecucion id={self.id} ejecucion_id={self.ejecucion_id} "
            f"accion={self.accion!r}>"
        )


class LoteOperacion(Base):
    """
    Lote de operaciones masivas (creación o eliminación) de entidades en Moodle.

    Agrupa un conjunto de ítems procesados mediante tareas Celery,
    con seguimiento de progreso por lote.
    """

    __tablename__ = "lotes_operacion"

    id = Column(Integer, primary_key=True, index=True)
    id_lote = Column(String(64), unique=True, index=True, nullable=False)
    tipo_entidad = Column(String(20), nullable=False)
    accion = Column(String(20), nullable=False)
    total = Column(Integer, default=0)
    completados = Column(Integer, default=0)
    fallidos = Column(Integer, default=0)
    modalidad = Column(String(20), nullable=False)
    creado_en = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    completado_en = Column(DateTime(timezone=True), nullable=True)

    items = relationship("ItemOperacion", back_populates="lote", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return (
            f"<LoteOperacion id={self.id} id_lote={self.id_lote!r} entidad={self.tipo_entidad!r}>"
        )


class ItemOperacion(Base):
    """
    Detalle individual de una operación dentro de un lote.

    Registra el estado, intentos y errores de cada entidad procesada.
    """

    __tablename__ = "items_operacion"

    id = Column(Integer, primary_key=True, index=True)
    id_lote = Column(String(64), ForeignKey("lotes_operacion.id_lote"), nullable=False, index=True)
    identificador = Column(String(255), nullable=False)
    estado = Column(String(20), nullable=False, default="pending", index=True)
    intento = Column(Integer, default=0)
    mensaje_error = Column(Text, nullable=True)
    detalle = Column(JSON, nullable=True)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    actualizado_en = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    lote = relationship("LoteOperacion", back_populates="items")

    def __repr__(self) -> str:
        return (
            f"<ItemOperacion id={self.id} identificador={self.identificador!r} "
            f"estado={self.estado!r}>"
        )


class ResultadoConsulta(Base):
    """
    Almacena el resultado de una consulta asíncrona a la API de Moodle.

    La consulta se ejecuta como tarea Celery y el resultado JSON
    completo queda almacenado para consulta y exportación CSV.
    """

    __tablename__ = "resultados_consulta"

    id = Column(Integer, primary_key=True, index=True)
    id_tarea = Column(String(64), unique=True, index=True, nullable=False)
    entidad = Column(String(20), nullable=False)
    parametros = Column(JSON, nullable=True)
    estado = Column(String(20), nullable=False, default="pending")
    resultado_json = Column(JSON, nullable=True)
    mensaje_error = Column(Text, nullable=True)
    conteo_total = Column(Integer, default=0)
    modalidad = Column(String(20), nullable=False)
    creado_en = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    completado_en = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<ResultadoConsulta id={self.id} entidad={self.entidad!r} id_tarea={self.id_tarea!r}>"
        )
