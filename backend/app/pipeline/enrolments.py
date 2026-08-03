"""Transformaciones sobre matrículas y creación de usuarios (FASE 2) — puras."""
from typing import Dict, List

Enrolment = Dict[str, object]
User = Dict[str, object]


def resolve_enrolments(
    enrolments: List[Enrolment],
    username_map: Dict[str, str],
) -> List[Enrolment]:
    """Reemplaza el username ETL por el username Moodle resuelto.

    Los usuarios sin resolución conservan su username ETL original.
    """
    resolved: List[Enrolment] = []
    for enr in enrolments:
        resolved_username = username_map.get(enr["username"], enr["username"])
        resolved.append({**enr, "username": resolved_username})
    return resolved


def users_to_create(
    etl_users: List[User],
    username_map: Dict[str, str],
) -> List[User]:
    """Usuarios ETL sin resolver en Moodle y con email institucional."""
    return [
        u for u in etl_users
        if u["username"] not in username_map
        and u.get("email", "").endswith("@ut.edu.co")
    ]
