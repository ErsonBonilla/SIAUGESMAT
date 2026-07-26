from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

class SemesterMetrics(BaseModel):
    semester: str
    total_executions: int
    total_courses_created: int
    total_users_created: int
    total_enrollments: int
    total_errors: int
    avg_duration_seconds: float
    last_completed: Optional[datetime] = None

class SemaphoreStatus(BaseModel):
    semester: str
    status: str  # green, yellow, red, gray
    error_rate: float
    avg_duration: float
    message: str

class LatestExecution(BaseModel):
    execution_id: int
    semester: str
    filename: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    metrics: Optional[Dict[str, Any]] = None
    errors_count: int
    error_rate: float
    semaphore: str
    moodle_version: Optional[str] = None
    modalidad: Optional[str] = None