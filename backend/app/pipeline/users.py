"""Resolución de usuarios (FASE 1) — transformaciones puras.

Sin I/O: los mapas de usuarios de Moodle (institucional, personal, username,
cédula) se reciben ya consultados y se devuelven eventos en lugar de persistir
logs directamente.
"""

import unicodedata

from app.pipeline.course_index import build_base_key
from app.pipeline.shortnames import parse_shortname

User = dict[str, object]
Event = tuple[str, str, dict[str, object]]


def pick_oldest_user(users: list[dict]) -> dict | None:
    """Selecciona el usuario más antiguo de una lista con el mismo identificador.

    Moodle puede devolver varios usuarios para un mismo email/username/cédula.
    Se elige el de menor ``timecreated``; por desempate, el de menor ``id``.
    Si ningún usuario trae ``timecreated`` (p. ej. ``core_user_get_users_by_field``
    no lo expone), se usa el menor ``id`` (los ids de Moodle son secuenciales y
    equivalen a antigüedad).

    Pura, sin I/O.
    """
    if not users:
        return None
    with_time = [u for u in users if (u.get("timecreated") or 0)]
    if with_time:
        return min(
            with_time,
            key=lambda u: (int(u.get("timecreated") or 0), int(u.get("id") or 0)),
        )
    return min(
        users,
        key=lambda u: (int(u.get("id") or 0), int(u.get("timecreated") or 0)),
    )


def normalize_name(name: str) -> str:
    """Normaliza un nombre para comparación: minúsculas y sin tildes."""
    text = "".join(
        c for c in unicodedata.normalize("NFD", name) if unicodedata.category(c) != "Mn"
    ).lower()
    return " ".join(text.split())


def names_differ(etl_name: str, moodle_name: str) -> bool:
    """Detecta si dos nombres de persona difieren significativamente."""
    a = normalize_name(etl_name)
    b = normalize_name(moodle_name)
    if not a or not b:
        return False
    if a == b:
        return False
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return True
    overlap = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    return overlap < 0.5


def resolve_users(
    etl_users: list[User],
    institutional_map: dict[str, User],
    personal_map: dict[str, User],
    username_index: dict[str, User],
    idnumber_index: dict[str, User],
) -> tuple[dict[str, str], list[Event]]:
    """Resuelve cada usuario ETL a un username de Moodle.

    Prioridad de matching: email institucional → email personal → username →
    cédula. Un match por username/cédula cuyo nombre difiere del de Moodle se
    marca como conflicto de identidad y no se mapea.

    Retorna (username_map, eventos):
      username_map: {username_etl: username_moodle_resuelto}
      eventos: lista de (tipo, identifier, detail), con tipo ∈
        {"user_identity_conflict", "user_resolved"}.
    """
    username_map: dict[str, str] = {}
    events: list[Event] = []

    for user in etl_users:
        email_lookup = user.get("email", "").strip().lower()
        personal_lookup = (user.get("email_personal") or "").strip().lower()
        uname = user.get("username", "")
        cedula = user.get("cedula", "")

        moodle_user = institutional_map.get(email_lookup)
        matched_by = "email"
        if not moodle_user:
            moodle_user = personal_map.get(personal_lookup)
            matched_by = "email_personal"
        if not moodle_user:
            moodle_user = username_index.get(uname)
            matched_by = "username"
        if not moodle_user:
            moodle_user = idnumber_index.get(str(cedula))
            matched_by = "cedula"
        if not moodle_user:
            continue

        resolved_username = moodle_user.get("username", "")
        if matched_by in ("username", "cedula"):
            etl_name = f"{user.get('firstname') or ''} {user.get('lastname') or ''}".strip()
            moodle_name = (
                f"{moodle_user.get('firstname') or ''} {moodle_user.get('lastname') or ''}"
            ).strip()
            if names_differ(etl_name, moodle_name):
                events.append(
                    (
                        "user_identity_conflict",
                        uname,
                        {
                            "email": email_lookup,
                            "etl_fullname": etl_name,
                            "moodle_fullname": moodle_name,
                            "matched_by": matched_by,
                        },
                    )
                )
                continue

        username_map[user["username"]] = resolved_username
        events.append(
            (
                "user_resolved",
                resolved_username,
                {
                    "email": user.get("email"),
                    "firstname": user.get("firstname", ""),
                    "lastname": user.get("lastname", ""),
                },
            )
        )

    return username_map, events


def index_teachers(
    users: list[User],
    enrolments: list[dict[str, str]],
) -> dict[str, dict[str, dict[object, list[str]]]]:
    """Construye índices de docentes por curso y por base_key.

    Cada índice agrupa emails, usernames e idnumbers de los docentes de cada
    curso, tanto por shortname exacto como por base_key (tupla parseada del
    shortname), para poder reutilizarlos en cursos homólogos.

    Retorna {"by_course": {...}, "by_base_key": {...}}.
    """
    users_by_username = {u["username"]: u for u in users}
    by_course = {"emails": {}, "usernames": {}, "idnumbers": {}}
    by_base_key = {"emails": {}, "usernames": {}, "idnumbers": {}}

    for enr in enrolments:
        sn = enr["course_shortname"]
        user = users_by_username.get(enr["username"])
        if not user:
            continue
        emails = [e for e in [user.get("email"), user.get("email_personal")] if e]
        by_course["emails"].setdefault(sn, []).extend(emails)
        by_course["usernames"].setdefault(sn, []).append(enr["username"])
        cedula = user.get("cedula", "")
        if cedula:
            by_course["idnumbers"].setdefault(sn, []).append(cedula)

        parsed = parse_shortname(sn)
        if parsed:
            bk = build_base_key(parsed)
            by_base_key["emails"].setdefault(bk, []).extend(emails)
            by_base_key["usernames"].setdefault(bk, []).append(enr["username"])
            if cedula:
                by_base_key["idnumbers"].setdefault(bk, []).append(cedula)

    return {"by_course": by_course, "by_base_key": by_base_key}


def lookup_teacher_candidates(
    shortname: str,
    teacher_index: dict[str, dict[str, dict[object, list[str]]]],
) -> tuple[list[str], list[str], list[str]]:
    """Recupera (emails, usernames, idnumbers) candidatos para un curso.

    Busca primero por shortname exacto; si no hay emails, cae a la base_key
    derivada del shortname (cursos homólogos).
    """
    by_course = teacher_index["by_course"]
    by_base_key = teacher_index["by_base_key"]

    emails = by_course["emails"].get(shortname, [])
    usernames = by_course["usernames"].get(shortname, [])
    idnumbers = by_course["idnumbers"].get(shortname, [])
    if not emails:
        parsed = parse_shortname(shortname)
        if parsed:
            bk = build_base_key(parsed)
            emails = by_base_key["emails"].get(bk, [])
            usernames = by_base_key["usernames"].get(bk, [])
            idnumbers = by_base_key["idnumbers"].get(bk, [])
    return emails, usernames, idnumbers
