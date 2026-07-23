"""
Modelos de base de datos (SQLAlchemy ORM) para SIAUGESMAT.

Define las tablas `executions` y `error_logs` utilizadas para el
seguimiento de los procesos ETL y el registro de errores.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class Execution(Base):
    """
    Representa una ejecución del proceso ETL a partir de un archivo Excel.

    Almacena el estado, el semestre, el modo (courses/users/both), las
    métricas finales y los tiempos de inicio y fin.
    """
    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(500), nullable=False)
    semester = Column(String(10), nullable=False)
    mode = Column(String(20), nullable=False, default="both")
    status = Column(String(20), nullable=False, default="pending")
    metrics = Column(JSON, nullable=True)
    errors_count = Column(Integer, default=0)
    report_dir = Column(String(500), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    current_phase = Column(String(100), nullable=True)
    progress_pct = Column(Float, nullable=True)
    current_step = Column(Integer, nullable=True)
    moodle_version = Column(String(10), nullable=True)
    modalidad = Column(String(20), nullable=True)
    phase_checkpoint = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    errors = relationship("ErrorLog", back_populates="execution", cascade="all, delete-orphan")
    logs = relationship("ExecutionLog", back_populates="execution", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Execution id={self.id} filename={self.filename!r} status={self.status!r}>"


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False)
    type = Column(String(50), nullable=False)
    identifier = Column(String(255), nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    execution = relationship("Execution", back_populates="errors")

    def __repr__(self) -> str:
        return f"<ErrorLog id={self.id} execution_id={self.execution_id} type={self.type!r}>"


class ExecutionLog(Base):
    """
    Registro detallado de acciones e incidencias durante una ejecución ETL.

    Almacena cada operación (creación, eliminación, activación, error, alerta)
    con datos estructurados para la generación de reportes.
    """
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id"), nullable=False)
    phase = Column(String(10), nullable=False)
    action = Column(String(50), nullable=False)
    identifier = Column(String(255), nullable=True)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    execution = relationship("Execution", back_populates="logs")

    def __repr__(self) -> str:
        return f"<ExecutionLog id={self.id} execution_id={self.execution_id} action={self.action!r}>"


class OperationBatch(Base):
    """
    Lote de operaciones masivas (creación o eliminación) de entidades en Moodle.

    Agrupa un conjunto de ítems procesados mediante tareas Celery,
    con seguimiento de progreso por lote.
    """
    __tablename__ = "operation_batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(64), unique=True, index=True, nullable=False)
    entity_type = Column(String(20), nullable=False)
    action = Column(String(20), nullable=False)
    total = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    modalidad = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    items = relationship("OperationItem", back_populates="batch", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<OperationBatch id={self.id} batch_id={self.batch_id!r} entity={self.entity_type!r}>"


class OperationItem(Base):
    """
    Detalle individual de una operación dentro de un lote.

    Registra el estado, intentos y errores de cada entidad procesada.
    """
    __tablename__ = "operation_items"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(64), ForeignKey("operation_batches.batch_id"), nullable=False, index=True)
    identifier = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempt = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(timezone.utc))

    batch = relationship("OperationBatch", back_populates="items")

    def __repr__(self) -> str:
        return f"<OperationItem id={self.id} identifier={self.identifier!r} status={self.status!r}>"


class QueryResult(Base):
    """
    Almacena el resultado de una consulta asíncrona a la API de Moodle.

    La consulta se ejecuta como tarea Celery y el resultado JSON
    completo queda almacenado para consulta y exportación CSV.
    """
    __tablename__ = "query_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(64), unique=True, index=True, nullable=False)
    entity = Column(String(20), nullable=False)
    params = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    total_count = Column(Integer, default=0)
    modalidad = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<QueryResult id={self.id} entity={self.entity!r} task_id={self.task_id!r}>"