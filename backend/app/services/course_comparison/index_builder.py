from typing import Dict, List, Tuple

from app.services.course_comparison.utils import build_base_key
from app.services.parsers.patterns import parse_shortname


def build_shortname_index(courses: List[Dict]) -> Dict[str, Dict]:
    return {c.get("shortname", ""): c for c in courses if c.get("shortname")}


def build_base_key_index(courses: List[Dict]) -> Dict[Tuple[str, ...], List[Dict]]:
    index: Dict[Tuple[str, ...], List[Dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parse_shortname(sn)
        if parsed:
            key = (parsed["cat_prefix"], parsed["cod_prog"], parsed["semestre"],
                   parsed["cod_curso"], parsed["grupo"])
            index.setdefault(key, []).append(c)
    return index


def build_core_index(courses: List[Dict]) -> Dict[Tuple[str, ...], List[Dict]]:
    index: Dict[Tuple[str, ...], List[Dict]] = {}
    for c in courses:
        sn = c.get("shortname", "")
        parsed = parse_shortname(sn)
        if parsed:
            key = (parsed["cod_prog"], parsed["cod_curso"], parsed["semestre"])
            index.setdefault(key, []).append(c)
    return index
