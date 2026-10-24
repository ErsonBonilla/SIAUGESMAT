"""Resolución de usuarios (FASE 1) — transformaciones puras.

Sin I/O: los mapas de usuarios de Moodle (institucional, personal, username,
cédula) se reciben ya consultados y se devuelven eventos en lugar de persistir
logs directamente.
"""

import unicodedata

from app.pipeline.indice_cursos import construir_clave_base
from app.pipeline.nombres_cortos import parsear_shortname

User = dict[str, object]
Event = tuple[str, str, dict[str, object]]


def elegir_usuario_mas_antiguo(users: list[dict]) -> dict | None:
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


def elegir_usuario_mas_reciente(users: list[dict]) -> dict | None:
    """Selecciona el usuario más reciente de una lista con el mismo identificador.

    Contraparte de ``pick_oldest_user``: elige el de mayor ``timecreated``; por
    desempate, el de mayor ``id``. Si ningún usuario trae ``timecreated`` se usa
    el mayor ``id`` (los ids de Moodle son secuenciales y equivalen a antigüedad).

    Pura, sin I/O.
    """
    if not users:
        return None
    with_time = [u for u in users if (u.get("timecreated") or 0)]
    if with_time:
        return max(
            with_time,
            key=lambda u: (int(u.get("timecreated") or 0), int(u.get("id") or 0)),
        )
    return max(
        users,
        key=lambda u: (int(u.get("id") or 0), int(u.get("timecreated") or 0)),
    )


def normalizar_nombre(name: str) -> str:
    """Normaliza un nombre para comparación: minúsculas y sin tildes."""
    text = "".join(
        c for c in unicodedata.normalize("NFD", name) if unicodedata.category(c) != "Mn"
    ).lower()
    return " ".join(text.split())


def nombres_difieren(etl_name: str, moodle_name: str) -> bool:
    """Detecta si dos nombres de persona difieren significativamente."""
    a = normalizar_nombre(etl_name)
    b = normalizar_nombre(moodle_name)
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


def resolver_usuarios(
    etl_users: list[User],
    institutional_map: dict[str, User],
    _personal_map: dict[str, User] | None = None,
    _username_index: dict[str, User] | None = None,
    _idnumber_index: dict[str, User] | None = None,
) -> tuple[dict[str, str], list[Event]]:
    """Resuelve cada usuario ETL a su username real en Moodle usando su correo @ut.edu.co.

    El username de Moodle puede diferir del prefijo antes de ``@ut.edu.co``;
    se respeta tal cual el username devuelto por Moodle para poder matricular
    al docente en sus cursos sin renombrar su cuenta.

    Retorna (username_map, eventos):
      username_map: {username_etl: username_moodle_resuelto}
      eventos: lista de (tipo, identifier, detail), con tipo == "user_resolved".
    """
    username_map: dict[str, str] = {}
    events: list[Event] = []

    for user in etl_users:
        email_lookup = str(user.get("email") or "").strip().lower()
        if not email_lookup.endswith("@ut.edu.co"):
            continue

        moodle_user = institutional_map.get(email_lookup)
        if not moodle_user:
            continue

        resolved_username = str(moodle_user.get("username") or "")
        if not resolved_username:
            continue

        username_map[str(user["username"])] = resolved_username
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


def indexar_docentes(
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

        parsed = parsear_shortname(sn)
        if parsed:
            bk = construir_clave_base(parsed)
            by_base_key["emails"].setdefault(bk, []).extend(emails)
            by_base_key["usernames"].setdefault(bk, []).append(enr["username"])
            if cedula:
                by_base_key["idnumbers"].setdefault(bk, []).append(cedula)

    return {"by_course": by_course, "by_base_key": by_base_key}


def buscar_candidatos_docente(
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
        parsed = parsear_shortname(shortname)
        if parsed:
            bk = construir_clave_base(parsed)
            emails = by_base_key["emails"].get(bk, [])
            usernames = by_base_key["usernames"].get(bk, [])
            idnumbers = by_base_key["idnumbers"].get(bk, [])
    return emails, usernames, idnumbers
