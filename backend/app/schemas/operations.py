from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CsvUploadResponse(BaseModel):
    batch_id: str
    entity_type: str
    action: str
    total: int
    message: str


class OperationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    identifier: str
    status: str
    error_message: str | None = None
    attempt: int


class BatchStatusResponse(BaseModel):
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
    details: list[OperationItemOut]


class BatchListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: str
    entity_type: str
    action: str
    total: int
    completed: int
    failed: int
    paused: int = 0
    modalidad: str
    created_at: datetime
    completed_at: datetime | None = None


class BatchListResponse(BaseModel):
    total: int
    items: list[BatchListOut]


class OperationMonthlyMetrics(BaseModel):
    month: str
    users_created: int = 0
    users_deleted: int = 0
    categories_created: int = 0
    categories_deleted: int = 0
    courses_deleted: int = 0
    total_errors: int = 0


class OperationsAnalyticsResponse(BaseModel):
    history: list[OperationMonthlyMetrics]


class DeleteOldBatchesResponse(BaseModel):
    deleted_batches: int
    older_than_days: int
