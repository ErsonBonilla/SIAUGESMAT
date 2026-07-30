import logging
from typing import Any, Dict, List, Set, Tuple

from app.services.course_comparison.index_builder import build_base_key_index, build_core_index, build_shortname_index
from app.services.course_comparison.action_handler import (
    handle_different_professor,
    handle_same_core_different_group,
    handle_same_professor,
)
from app.services.course_comparison.disappeared import find_disappeared_courses
from app.services.course_comparison.apply_action import apply_action
from app.services.course_comparison.utils import get_course_professor, get_suffix, parse_sn
from app.services.parsers.patterns import SIAUGESMAT_PATTERN, parse_shortname

logger = logging.getLogger(__name__)


class CourseComparisonService:

    @classmethod
    async def compare(
        cls,
        existing_courses: List[Dict],
        new_courses: List[Dict],
        new_enrolments: List[Dict],
        re_upload: bool = False,
        courses_with_teacher: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        if courses_with_teacher is None:
            courses_with_teacher = {}
        siaugesmat_courses = [
            c for c in existing_courses
            if SIAUGESMAT_PATTERN.match(c.get("shortname", ""))
        ]

        existing_by_shortname = build_shortname_index(siaugesmat_courses)
        existing_by_base_key = build_base_key_index(siaugesmat_courses)
        existing_by_core = build_core_index(siaugesmat_courses)

        enrolment_index: Dict[str, str] = {}
        for enr in new_enrolments:
            enrolment_index[enr["course_shortname"]] = enr["username"]

        to_create: List[Dict] = []
        to_delete: List[str] = []
        to_activate: List[str] = []
        to_hide: List[str] = []
        to_update: List[Dict] = []
        alerts: List[Dict] = []
        logs: List[Dict] = []

        new_shortnames = set()
        new_base_keys = set()

        new_groups_by_core: Dict[Tuple[str, ...], set] = {}
        new_program_codes: Set[str] = set()
        for course in new_courses:
            parsed = parse_shortname(course["shortname"])
            if parsed:
                core_key = (parsed["cod_prog"], parsed["cod_curso"], parsed["semestre"])
                new_groups_by_core.setdefault(core_key, set()).add(parsed["grupo"])
                new_program_codes.add(parsed["cod_prog"])

        for course in new_courses:
            sn = course["shortname"]
            new_shortnames.add(sn)
            parsed_new = parse_shortname(sn)
            professor = enrolment_index.get(sn, "")
            new_suffix = parsed_new.get("suffix", "") if parsed_new else ""

            if sn in existing_by_shortname:
                existing = existing_by_shortname[sn]
                existing_prof = get_course_professor(existing)

                if sn not in courses_with_teacher:
                    action, detail = "recreate", {
                        "reason": "orphan_course",
                        "old_shortname": existing.get("shortname", sn),
                        "professor": professor,
                        "old_professor": existing_prof or "",
                    }
                elif (existing_prof and existing_prof == professor) or courses_with_teacher.get(sn) == professor:
                    action, detail = handle_same_professor(existing, sn, professor)
                else:
                    action, detail = handle_different_professor(
                        existing, sn, professor, existing_prof,
                        should_hide_existing=True,
                        re_upload=re_upload,
                    )

            elif parsed_new:
                base_key = cls._build_base_key_from_parsed(parsed_new)
                new_base_keys.add(base_key)
                candidates = existing_by_base_key.get(base_key, [])

                if candidates:
                    match = next(
                        (c for c in candidates
                         if get_suffix(c.get("shortname", "")) == new_suffix),
                        None,
                    )
                    if match:
                        existing_prof = get_course_professor(match)
                        if existing_prof and existing_prof == professor:
                            action, detail = handle_same_professor(match, sn, professor)
                        else:
                            action, detail = handle_different_professor(
                                match, sn, professor, existing_prof,
                                re_upload=re_upload,
                            )
                    elif new_suffix:
                        match = next(
                            (c for c in candidates
                             if get_course_professor(c) == professor
                             or (c.get("shortname", "") in courses_with_teacher
                                 and courses_with_teacher[c.get("shortname", "")] == professor)),
                            None,
                        )
                        if match:
                            old_hidden = cls._is_course_hidden_by_field(match)
                            action, detail = "rename_group", {
                                "reason": "suffix_update",
                                "professor": professor,
                                "old_shortname": match["shortname"],
                                "old_suffix": get_suffix(match["shortname"]),
                                "new_suffix": new_suffix,
                                "reactivate": old_hidden,
                            }
                        else:
                            target = cls._first_visible_candidate(candidates)
                            existing_prof = get_course_professor(target)
                            action, detail = handle_different_professor(
                                target, sn, professor, existing_prof,
                                should_hide_existing=True,
                                re_upload=re_upload,
                            )
                    else:
                        target = cls._first_visible_candidate(candidates)
                        existing_prof = get_course_professor(target)
                        action, detail = handle_different_professor(
                            target, sn, professor, existing_prof,
                            should_hide_existing=True,
                            re_upload=re_upload,
                        )
                else:
                    core_key = (
                        parsed_new["cod_prog"],
                        parsed_new["cod_curso"],
                        parsed_new["semestre"],
                    )
                    same_core_courses = existing_by_core.get(core_key, [])

                    if same_core_courses:
                        action, detail = handle_same_core_different_group(
                            same_core_courses, parsed_new, sn, professor, new_groups_by_core
                        )
                    else:
                        action, detail = "create", {"reason": "new", "professor": professor}
            else:
                action, detail = "create", {"reason": "new", "professor": professor}

            apply_action(
                action, detail, sn, professor, parsed_new,
                to_create, to_delete, to_activate, to_hide, to_update, alerts, logs,
            )

        find_disappeared_courses(
            existing_by_shortname, existing_by_base_key, new_shortnames, new_base_keys,
            new_program_codes, to_delete, to_hide, alerts, logs,
        )

        return {
            "to_create": to_create,
            "to_delete": to_delete,
            "to_activate": to_activate,
            "to_hide": to_hide,
            "to_update": to_update,
            "alerts": alerts,
            "logs": logs,
        }

    @staticmethod
    def _build_base_key_from_parsed(parsed: Dict) -> Tuple[str, ...]:
        return (
            parsed["cat_prefix"],
            parsed["cod_prog"],
            parsed["semestre"],
            parsed["cod_curso"],
            parsed["grupo"],
        )

    @staticmethod
    def _is_course_hidden_by_field(course: Dict) -> bool:
        return course.get("visible", 1) == 0

    @staticmethod
    def _first_visible_candidate(candidates: List[Dict]) -> Dict:
        for c in candidates:
            if c.get("visible", 1) == 1:
                return c
        return candidates[0]
