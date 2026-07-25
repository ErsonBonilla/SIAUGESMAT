from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

from app.integrations.moodle import MoodleIntegration
from app.services.moodle import MoodleOverloadedError, MoodleService


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
        self.all_categories_map: Dict[str, Dict] = {}
        self.existing_courses: List[Dict] = []
        self.username_map: Dict[str, str] = {}
        self.courses_with_teacher: Set[str] = set()

        self.re_upload: bool = False
        self.missing_categories: List[Dict] = []
        self.categories_to_relocate: List[Dict] = []
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
