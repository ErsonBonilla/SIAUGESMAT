"""
Adaptadores de versión para la API REST de Moodle.

Implementa el patrón Adapter para manejar diferencias entre versiones
de Moodle (3.x) en los web services que cambian entre versiones.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from app.services.roles import resolve_role, role_shortname_to_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tipo para la función de llamada WS (MoodleService._request)
# ---------------------------------------------------------------------------
WSFunc = Callable[[str, Dict[str, Any]], Any]


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
        "4.0": Moodle3Adapter,
        "4.1": Moodle3Adapter,
        "4.2": Moodle3Adapter,
        "4.3": Moodle3Adapter,
        "4.4": Moodle3Adapter,
        "4.5": Moodle3Adapter,
    }
    # NOTA: Las versiones 4.x se mapean a Moodle3Adapter por compatibilidad observada.
    # Si Moodle 4.x introduce cambios en core_course_get_courses_by_field,
    # core_enrol_get_course_enrolment_methods o core_course_create_courses,
    # se debe crear Moodle4Adapter y actualizar este mapeo.

    @classmethod
    def create(cls, version: str) -> MoodleAdapter:
        if version in cls._adapters:
            adapter_cls = cls._adapters[version]
        else:
            # Normalizar: "3.9.3" → "3.9", "3.9+" → "3.9"
            import re
            match = re.match(r"^(\d+\.\d+)", version.replace("+", ""))
            normalized = match.group(1) if match else version
            adapter_cls = cls._adapters.get(normalized)
            if adapter_cls is None:
                raise ValueError(f"Unsupported Moodle version: {version}")
            logger.debug("Normalized version '%s' -> '%s'", version, normalized)
        logger.debug("Using adapter %s for Moodle %s", adapter_cls.__name__, version)
        return adapter_cls()
