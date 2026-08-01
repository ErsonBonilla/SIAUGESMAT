import re
from typing import Dict, Match, Optional

SIAUGESMAT_PATTERN = re.compile(
    r"^[A-Z]{3}_\d{4}_(?:\d+_s[IVXLCDM]+|s[IVXLCDM]+_\d+)_G-[^_]+(?:_[^_]+)?$",
    re.IGNORECASE,
)

SHORTNAME_PATTERN = re.compile(
    r"^(?P<cat_prefix>[A-Z]+)_(?P<cod_prog>\d{4})_"
    r"(?:"
    r"(?P<cod_curso_old>\d+)_s(?P<semestre_old>[IVXLCDM]+)|"
    r"s(?P<semestre_new>[IVXLCDM]+)_(?P<cod_curso_new>\d+)"
    r")_"
    r"G-(?P<grupo>[^_]+)(?:_(?P<suffix>[^_]+))?$",
    re.IGNORECASE,
)


def parse_shortname(shortname: str) -> Optional[Dict[str, str]]:
    m = SHORTNAME_PATTERN.match(shortname)
    if not m:
        return None
    return {
        "cat_prefix": m.group("cat_prefix"),
        "cod_prog": m.group("cod_prog"),
        "semestre": m.group("semestre_new") or m.group("semestre_old") or "",
        "cod_curso": m.group("cod_curso_new") or m.group("cod_curso_old") or "",
        "grupo": m.group("grupo"),
        "suffix": m.group("suffix"),
    }
