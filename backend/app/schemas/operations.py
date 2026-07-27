from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional


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
    error_message: Optional[str] = None
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
    offset: int = 0
    limit: int = 100
    details: List[OperationItemOut]


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
    completed_at: Optional[datetime] = None


class BatchListResponse(BaseModel):
    total: int
    items: List[BatchListOut]


class OperationMonthlyMetrics(BaseModel):
    month: str
    users_created: int = 0
    users_deleted: int = 0
    categories_created: int = 0
    categories_deleted: int = 0
    courses_deleted: int = 0
    total_errors: int = 0


class OperationsAnalyticsResponse(BaseModel):
    history: List[OperationMonthlyMetrics]


class DeleteOldBatchesResponse(BaseModel):
    deleted_batches: int
    older_than_days: int
