"""
Adaptadores de versión para la API REST de Moodle.

Implementa el patrón Adapter para manejar diferencias entre versiones
de Moodle (3.x) en los web services que cambian entre versiones.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tipo para la función de llamada WS (MoodleService._request)
# ---------------------------------------------------------------------------
WSFunc = Callable[[str, Dict[str, Any]], Any]


def role_shortname_to_id(shortname: str) -> int:
    """Convierte el nombre corto de un rol a su ID estándar de Moodle."""
    mapping = {
        "student": 5,
        "editingteacher": 3,
        "teacher": 4,
        "manager": 1,
    }
    return mapping.get(shortname, 5)


def resolve_role(value: str) -> int:
    """Convierte un rol (shortname o roleid numérico) a roleid de Moodle."""
    try:
        role_id = int(value)
        if role_id in (1, 3, 4, 5):
            return role_id
    except ValueError:
        pass
    return role_shortname_to_id(value.strip().lower())


# ---------------------------------------------------------------------------
# Clase base abstracta
# ---------------------------------------------------------------------------
class MoodleAdapter(ABC):
    """
    Define los métodos que pueden variar entre versiones de Moodle.
    Cada método recibe ``call_ws`` para invocar web services si es necesario.
    """

    @abstractmethod
    async def enable_self_enrolment(self, course_id: int, call_ws: WSFunc) -> Dict:
        """Activa la auto-matriculación en un curso."""

    @abstractmethod
    async def get_courses(
        self, shortname: Optional[str], call_ws: WSFunc
    ) -> List[Dict]:
        """Obtiene cursos, con opciones específicas de versión."""

    @abstractmethod
    def build_create_course_enrolment_params(
        self, params: Dict, course: Dict, index: int
    ) -> None:
        """Agrega parámetros de matriculación a la creación de un curso."""


# ---------------------------------------------------------------------------
# Adaptador para Moodle 3.x (3.8, 3.9)
# ---------------------------------------------------------------------------
class Moodle3Adapter(MoodleAdapter):
    """
    Comportamiento para Moodle 3.x.
    - No existe enrol_self_edit_instance (la auto-matriculación se crea por defecto).
    - customfields debe solicitarse explícitamente en get_courses.
    """

    async def enable_self_enrolment(self, course_id: int, call_ws: WSFunc) -> Dict:
        enrols = await call_ws(
            "core_enrol_get_course_enrolment_methods",
            {"courseid": course_id},
        )
        existing = [e for e in enrols if e.get("type") == "self"]
        if not existing:
            raise ValueError(
                f"Enrolment 'self' no encontrado para curso {course_id} "
                "(Moodle 3.x no permite crearla vía WS)"
            )
        return existing[0]

    async def get_courses(
        self, shortname: Optional[str], call_ws: WSFunc
    ) -> List[Dict]:
        if shortname:
            result = await call_ws("core_course_get_courses_by_field", {
                "field": "shortname",
                "value": shortname,
            })
        else:
            result = await call_ws("core_course_get_courses", {})
        if isinstance(result, dict):
            return result.get("courses", [])
        return result

    def build_create_course_enrolment_params(
        self, params: Dict, course: Dict, index: int
    ) -> None:
        pass  # Moodle 3.9 no acepta enrolment_1 como parametro de core_course_create_courses


# ---------------------------------------------------------------------------
# Fábrica de adaptadores
# ---------------------------------------------------------------------------
class MoodleAdapterFactory:
    """
    Crea el adaptador correspondiente según la versión de Moodle.
    """

    _adapters: Dict[str, type] = {
        "3.8": Moodle3Adapter,
        "3.9": Moodle3Adapter,
    }

    @classmethod
    def create(cls, version: str) -> MoodleAdapter:
        adapter_cls = cls._adapters.get(version)
        if adapter_cls is None:
            raise ValueError(f"Unsupported Moodle version: {version}")
        logger.debug("Using adapter %s for Moodle %s", adapter_cls.__name__, version)
        return adapter_cls()
