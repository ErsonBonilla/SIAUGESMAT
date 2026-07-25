from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

import httpx

from app.integrations.moodle import MoodleIntegration
from app.services.moodle import MoodleAPIError, MoodleService


class MoodleOverloadedError(Exception):
    """El servidor de Moodle está sobrecargado. Celery reintentará la tarea."""


def is_moodle_overloaded(e: BaseException) -> bool:
    """Retorna True si el error es transitorio (servidor sobrecargado, timeout, o errores DB de Moodle)."""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in (502, 503, 504)
    if isinstance(e, httpx.ConnectError):
        return True
    if isinstance(e, httpx.ReadTimeout):
        return True
    inner = e
    if hasattr(e, 'last_attempt'):
        try:
            inner = e.last_attempt.exception() or inner
        except Exception:
            pass
    if isinstance(inner, MoodleAPIError):
        if inner.error_code in ("invalidrecord", "storedfilenotcreated", "invalidcoursemodule"):
            return True
    msg = str(e).lower()
    return any(kw in msg for kw in ("gateway time-out", "connect error", "read timeout", "connection refused"))


class PhaseContext:
    def __init__(
        self,
        db,
        execution_id: int,
        execution,
        mode: str,
        semester: str,
        etl_data: Dict[str, Any],
        moodle_service: MoodleService,
        integration: MoodleIntegration,
    ):
        self.db = db
        self.execution_id = execution_id
        self.execution = execution
        self.mode = mode
        self.semester = semester
        self.etl_data = etl_data
        self.moodle_service = moodle_service
        self.integration = integration

        self.existing_cat_idnumbers: Set[str] = set()
        self.existing_courses: List[Dict] = []
        self.username_map: Dict[str, str] = {}
        self.courses_with_teacher: Set[str] = set()

        self.re_upload: bool = False
        self.missing_categories: List[Dict] = []
        self.comparison: Dict[str, Any] = {}
        self.users_to_create: List[Dict] = []
        self.resolved_enrolments: List[Dict] = []

        self.structure_progress: Dict[str, Any] = {}
        self.people_progress: Dict[str, Any] = {}

        self.metrics: Dict[str, int] = {
            "categories_created": 0,
            "courses_created": 0,
            "courses_deleted": 0,
            "courses_activated": 0,
            "courses_hidden": 0,
            "users_created": 0,
            "enrolments": 0,
            "enrolment_errors": 0,
            "alerts": 0,
            "total_errors": 0,
        }


class BasePhase(ABC):
    phase_name: str = ""

    @abstractmethod
    async def run(self, ctx: PhaseContext) -> None:
        ...
