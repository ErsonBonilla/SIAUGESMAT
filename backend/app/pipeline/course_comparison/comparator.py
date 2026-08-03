import logging
from typing import Any

from app.pipeline.course_comparison.action_handler import (
    handle_different_professor,
    handle_same_core_different_group,
    handle_same_professor,
)
from app.pipeline.course_comparison.apply_action import apply_action
from app.pipeline.course_comparison.disappeared import find_disappeared_courses
from app.pipeline.course_comparison.index_builder import (
    build_base_key_index,
    build_core_index,
    build_shortname_index,
)
from app.pipeline.course_comparison.thresholds import (
    DEFAULT_COURSE_DISAPPEARED_AGE_SECONDS,
    DEFAULT_COURSE_MAX_AGE_SECONDS,
)
from app.pipeline.course_comparison.utils import (
    build_base_key,
    build_enrolment_map,
    first_visible,
    get_course_professor,
    get_suffix,
    is_course_hidden,
)
from app.pipeline.shortnames import SIAUGESMAT_PATTERN, parse_shortname

logger = logging.getLogger(__name__)


class CourseComparisonService:

    @classmethod
    async def compare(
        cls,
        existing_courses: list[dict],
        new_courses: list[dict],
        new_enrolments: list[dict],
        re_upload: bool = False,
        courses_with_teacher: dict[str, str] = None,
        *,
        max_age_seconds: int = DEFAULT_COURSE_MAX_AGE_SECONDS,
        disappeared_age_seconds: int = DEFAULT_COURSE_DISAPPEARED_AGE_SECONDS,
    ) -> dict[str, Any]:
        if courses_with_teacher is None:
            courses_with_teacher = {}
        siaugesmat_courses = [
            c for c in existing_courses
            if SIAUGESMAT_PATTERN.match(c.get("shortname", ""))
        ]

        existing_by_shortname = build_shortname_index(siaugesmat_courses)
        existing_by_base_key = build_base_key_index(siaugesmat_courses)
        existing_by_core = build_core_index(siaugesmat_courses)

        enrolment_index = build_enrolment_map(new_enrolments)

        to_create: list[dict] = []
        to_delete: list[str] = []
        to_activate: list[str] = []
        to_hide: list[str] = []
        to_update: list[dict] = []
        alerts: list[dict] = []
        logs: list[dict] = []

        new_shortnames = set()
        new_base_keys = set()

        new_groups_by_core: dict[tuple[str, ...], set] = {}
        new_program_codes: set[str] = set()
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
                    action, detail = handle_same_professor(
                        existing, sn, professor,
                        max_age_seconds=max_age_seconds,
                    )
                else:
                    action, detail = handle_different_professor(
                        existing, sn, professor, existing_prof,
                        should_hide_existing=True,
                        re_upload=re_upload,
                        max_age_seconds=max_age_seconds,
                    )

            elif parsed_new:
                base_key = build_base_key(parsed_new)
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
                            action, detail = handle_same_professor(
                                match, sn, professor,
                                max_age_seconds=max_age_seconds,
                            )
                        else:
                            action, detail = handle_different_professor(
                                match, sn, professor, existing_prof,
                                re_upload=re_upload,
                                max_age_seconds=max_age_seconds,
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
                            old_hidden = is_course_hidden(match)
                            action, detail = "rename_group", {
                                "reason": "suffix_update",
                                "professor": professor,
                                "old_shortname": match["shortname"],
                                "old_suffix": get_suffix(match["shortname"]),
                                "new_suffix": new_suffix,
                                "reactivate": old_hidden,
                            }
                        else:
                            target = first_visible(candidates)
                            existing_prof = get_course_professor(target)
                            action, detail = handle_different_professor(
                                target, sn, professor, existing_prof,
                                should_hide_existing=True,
                                re_upload=re_upload,
                                max_age_seconds=max_age_seconds,
                            )
                    else:
                        target = first_visible(candidates)
                        existing_prof = get_course_professor(target)
                        action, detail = handle_different_professor(
                            target, sn, professor, existing_prof,
                            should_hide_existing=True,
                            re_upload=re_upload,
                            max_age_seconds=max_age_seconds,
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
            disappeared_age_seconds=disappeared_age_seconds,
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
