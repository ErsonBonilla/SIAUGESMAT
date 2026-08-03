from typing import Dict, List, Set, Tuple

from app.pipeline.course_comparison.thresholds import (
    DEFAULT_COURSE_DISAPPEARED_AGE_SECONDS,
)
from app.pipeline.course_comparison.utils import (
    build_base_key,
    get_course_age_seconds,
    is_course_hidden,
)
from app.pipeline.shortnames import parse_shortname


def find_disappeared_courses(
    existing_by_shortname: Dict[str, Dict],
    existing_by_base_key: Dict[Tuple[str, ...], List[Dict]],
    new_shortnames: set,
    new_base_keys: set,
    new_program_codes: Set[str],
    to_delete: List[str],
    to_hide: List[str],
    alerts: List[Dict],
    logs: List[Dict],
    *,
    disappeared_age_seconds: int = DEFAULT_COURSE_DISAPPEARED_AGE_SECONDS,
):
    for sn, existing in existing_by_shortname.items():
        if sn in new_shortnames:
            continue

        parsed = parse_shortname(sn)
        if parsed:
            if parsed["cod_prog"] not in new_program_codes:
                continue
            base_key = build_base_key(parsed)
            if base_key in new_base_keys:
                continue

        age = get_course_age_seconds(existing)
        if age >= disappeared_age_seconds:
            to_delete.append({
                "shortname": sn,
                "reason": "disappeared",
                "age_seconds": age,
                "fullname": existing.get("fullname", ""),
            })
            alerts.append({
                "shortname": sn,
                "reason": "disappeared",
                "age_seconds": age,
            })
            logs.append({
                "phase": "2",
                "action": "course_deleted",
                "identifier": sn,
                "detail": {"reason": "disappeared", "age_seconds": age},
            })
        elif not is_course_hidden(existing):
            to_hide.append({
                "shortname": sn,
                "reason": "disappeared_recent",
                "age_seconds": age,
                "fullname": existing.get("fullname", ""),
            })
            alerts.append({
                "shortname": sn,
                "reason": "disappeared_recent",
                "age_seconds": age,
            })
            logs.append({
                "phase": "2",
                "action": "course_disappeared_recent_hidden",
                "identifier": sn,
                "detail": {"reason": "disappeared_recent", "age_seconds": age},
            })
