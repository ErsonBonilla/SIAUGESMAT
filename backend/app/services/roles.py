"""
Utilidades para resolución de roles de Moodle.
Centraliza el mapeo de role_shortname → role_id para evitar
duplicación entre moodle_adapter.py y moodle.py.
"""

import logging

logger = logging.getLogger(__name__)

ROLE_MAPPING: dict[str, int] = {
    "student": 5,
    "editingteacher": 3,
    "teacher": 4,
    "manager": 1,
}


def role_shortname_to_id(shortname: str) -> int:
    """Convierte el nombre corto de un rol a su ID estándar de Moodle."""
    role_id = ROLE_MAPPING.get(shortname)
    if role_id is None:
        logger.warning(f"Rol desconocido '{shortname}', usando 'student' (5)")
        return 5
    return role_id


def resolve_role(value: str) -> int:
    """Convierte un rol (shortname o roleid numérico) a roleid de Moodle."""
    try:
        role_id = int(value)
        if role_id in ROLE_MAPPING.values():
            return role_id
    except ValueError:
        pass
    return role_shortname_to_id(value.strip().lower())
