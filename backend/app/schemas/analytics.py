from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SemesterMetrics(BaseModel):
    semester: str
    total_executions: int
    total_courses_created: int
    total_users_created: int
    total_enrollments: int
    total_errors: int
    avg_duration_seconds: float
    last_completed: datetime | None = None

class SemaphoreStatus(BaseModel):
    semester: str
    status: str  # green, yellow, red, gray
    error_rate: float
    avg_duration: float
    message: str

class LatestExecution(BaseModel):
    id: int
    semester: str
    filename: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    metrics: dict[str, Any] | None = None
    errors_count: int
    error_rate: float
    semaphore: str
    moodle_version: str | None = None
    modalidad: str | None = None
