
from app.pipeline.course_comparison.thresholds import DEFAULT_COURSE_MAX_AGE_SECONDS
from app.pipeline.course_comparison.utils import (
    get_course_age_seconds,
    get_course_professor,
    is_course_hidden,
)
from app.pipeline.shortnames import parse_shortname


def handle_same_professor(
    existing: dict,
    sn: str,
    professor: str,
    *,
    max_age_seconds: int = DEFAULT_COURSE_MAX_AGE_SECONDS,
) -> tuple[str, dict]:
    age = get_course_age_seconds(existing)
    existing_sn = existing.get("shortname", "")
    needs_rename = existing_sn != sn

    if age >= max_age_seconds:
        return "recreate", {
            "reason": "old_course_cleanup",
            "professor": professor,
            "age_seconds": age,
        }

    if is_course_hidden(existing):
        if needs_rename:
            return "rename_group", {
                "reason": "same_professor_hidden_rename",
                "professor": professor,
                "old_shortname": existing_sn,
                "new_shortname": sn,
                "reactivate": True,
            }
        return "activate", {
            "reason": "same_professor_hidden",
            "professor": professor,
        }

    if needs_rename:
        return "rename_group", {
            "reason": "same_professor_cedula_update",
            "professor": professor,
            "old_shortname": existing_sn,
            "new_shortname": sn,
        }
    return "none", {"reason": "same_professor", "professor": professor}


def handle_different_professor(
    existing: dict,
    sn: str,
    new_prof: str,
    old_prof: str | None,
    should_hide_existing: bool = False,
    re_upload: bool = False,
    *,
    max_age_seconds: int = DEFAULT_COURSE_MAX_AGE_SECONDS,
) -> tuple[str, dict]:
    age = get_course_age_seconds(existing)
    detail = {
        "reason": "teacher_change",
        "old_shortname": existing.get("shortname", ""),
        "old_professor": old_prof or "",
        "new_professor": new_prof,
        "age_seconds": age,
    }

    if re_upload:
        detail["reason"] = "teacher_change_re_upload"
        return "recreate", detail

    if age >= max_age_seconds:
        detail["reason"] = "teacher_change_old"
        return "recreate", detail
    detail["reason"] = "teacher_change_recent"
    if should_hide_existing:
        return "hide_and_create", detail
    return "recreate", detail


def handle_same_core_different_group(
    same_core_courses: list[dict],
    parsed_new: dict,
    sn: str,
    professor: str,
    new_groups_by_core: dict[tuple[str, ...], set],
) -> tuple[str, dict]:
    core_key = (parsed_new["cod_prog"], parsed_new["cod_curso"], parsed_new["semestre"])
    new_groups = new_groups_by_core.get(core_key, set())

    for existing in same_core_courses:
        existing_sn = existing.get("shortname", "")
        parsed_existing = parse_shortname(existing_sn)
        if not parsed_existing:
            continue
        existing_group = parsed_existing["grupo"]
        new_group = parsed_new["grupo"]

        if existing_group == new_group:
            continue

        existing_prof = get_course_professor(existing)
        template = existing_sn

        if existing_prof and existing_prof == professor:
            if existing_group not in new_groups:
                entry = {
                    "reason": "same_professor_group_changed",
                    "professor": professor,
                    "old_shortname": existing_sn,
                    "old_group": existing_group,
                    "new_group": new_group,
                }
                if is_course_hidden(existing):
                    entry["reactivate"] = True
                return "rename_group", entry
            return "create_with_template", {
                "reason": "same_professor_new_group",
                "professor": professor,
                "group_origin": existing_group,
                "group_new": new_group,
                "template_shortname": template,
            }
        return "create", {
            "reason": "different_professor_new_group",
            "professor": professor,
            "group_origin": existing_group,
            "group_new": new_group,
        }

    return "create", {"reason": "new", "professor": professor}
