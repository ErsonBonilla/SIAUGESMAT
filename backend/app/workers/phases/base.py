from abc import ABC, abstractmethod
from typing import Any

from app.integrations.moodle import MoodleIntegration
from app.services.moodle_errors import MoodleOverloadedError as MoodleOverloadedError
from app.services.moodle_operations import MoodleService

__all__ = ["MoodleOverloadedError", "PhaseContext"]


class PhaseContext:
    def __init__(
        self,
        db,
        execution_id: int,
        execution,
        mode: str,
        semester: str,
        etl_data: dict[str, Any],
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

        self.existing_cat_idnumbers: set[str] = set()
        self.all_categories_map: dict[str, dict] = {}
        self.existing_courses: list[dict] = []
        self.username_map: dict[str, str] = {}
        self.courses_with_teacher: dict[str, str] = {}
        self.course_teacher_map: dict[str, str] = {}

        self.re_upload: bool = False
        self.missing_categories: list[dict] = []
        self.categories_to_relocate: list[dict] = []
        self.comparison: dict[str, Any] = {}
        self.users_to_create: list[dict] = []
        self.resolved_enrolments: list[dict] = []

        self.structure_progress: dict[str, Any] = {}
        self.people_progress: dict[str, Any] = {}

        self.metrics: dict[str, int] = {
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
