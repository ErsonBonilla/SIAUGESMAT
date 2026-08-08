"""Transformaciones sobre matrículas y creación de usuarios (FASE 2) — puras."""

Enrolment = dict[str, object]
User = dict[str, object]


def resolve_enrolments(
    enrolments: list[Enrolment],
    username_map: dict[str, str],
) -> list[Enrolment]:
    """Reemplaza el username ETL por el username Moodle resuelto.

    Los usuarios sin resolución conservan su username ETL original.
    """
    resolved: list[Enrolment] = []
    for enr in enrolments:
        resolved_username = username_map.get(enr["username"], enr["username"])
        resolved.append({**enr, "username": resolved_username})
    return resolved


def users_to_create(
    etl_users: list[User],
    username_map: dict[str, str],
) -> list[User]:
    """Usuarios ETL sin resolver en Moodle y con email institucional."""
    return [
        u
        for u in etl_users
        if u["username"] not in username_map and u.get("email", "").endswith("@ut.edu.co")
    ]
