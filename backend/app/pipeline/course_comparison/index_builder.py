
from app.pipeline.course_comparison.utils import build_base_key
from app.pipeline.shortnames import parse_shortname


def build_shortname_index(courses: list[dict]) -> dict[str, dict]:
    return {c.get("shortname", ""): c for c in courses if c.get("shortname")}


def build_base_key_index(courses: list[dict]) -> dict[tuple[str, ...], list[dict]]:
    index: dict[tuple[str, ...], list[dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parse_shortname(sn)
        if parsed:
            key = build_base_key(parsed)
            index.setdefault(key, []).append(c)
    return index


def build_core_index(courses: list[dict]) -> dict[tuple[str, ...], list[dict]]:
    index: dict[tuple[str, ...], list[dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parse_shortname(sn)
        if parsed:
            key = (parsed["cod_prog"], parsed["cod_curso"], parsed["semestre"])
            index.setdefault(key, []).append(c)
    return index
