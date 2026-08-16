"""
Adaptadores de versión para la API REST de Moodle.

Implementa el patrón Adapter para manejar diferencias entre versiones
de Moodle (3.x) en los web services que cambian entre versiones.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, ClassVar

from app.services.roles import rol_shortname_a_id as rol_shortname_a_id

__all__ = ["AdaptadorMoodle", "AdaptadorMoodle3", "FabricaAdaptadorMoodle", "rol_shortname_a_id"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tipo para la función de llamada WS (MoodleService._solicitar)
# ---------------------------------------------------------------------------
WSFunc = Callable[[str, dict[str, Any]], Any]


# ---------------------------------------------------------------------------
# Clase base abstracta
# ---------------------------------------------------------------------------
class AdaptadorMoodle(ABC):
    """
    Define los métodos que pueden variar entre versiones de Moodle.
    Cada método recibe ``call_ws`` para invocar web services si es necesario.
    """

    @abstractmethod
    async def habilitar_automatriculacion(self, course_id: int, llamar_ws: WSFunc) -> dict:
        """Activa la auto-matriculación en un curso."""

    @abstractmethod
    async def obtener_cursos(self, shortname: str | None, llamar_ws: WSFunc) -> list[dict]:
        """Obtiene cursos, con opciones específicas de versión."""

    @abstractmethod
    def construir_parametros_matriculacion_curso(
        self, params: dict, course: dict, index: int
    ) -> None:
        """Agrega parámetros de matriculación a la creación de un curso."""

        # ---------------------------------------------------------------------------
        # Adaptador para Moodle 3.x (3.8, 3.9)
        # ---------------------------------------------------------------------------


class AdaptadorMoodle3(AdaptadorMoodle):
    """
    Comportamiento para Moodle 3.x.
    - No existe enrol_self_edit_instance (la auto-matriculación se crea por defecto).
    - customfields debe solicitarse explícitamente en get_courses.
    """

    async def habilitar_automatriculacion(self, course_id: int, llamar_ws: WSFunc) -> dict:
        enrols = await llamar_ws(
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

    async def obtener_cursos(self, shortname: str | None, llamar_ws: WSFunc) -> list[dict]:
        if shortname:
            result = await llamar_ws(
                "core_course_get_courses_by_field",
                {
                    "field": "shortname",
                    "value": shortname,
                },
            )
        else:
            result = await llamar_ws("core_course_get_courses", {})
        if isinstance(result, dict):
            return result.get("courses", [])
        return result

    def construir_parametros_matriculacion_curso(
        self, params: dict, course: dict, index: int
    ) -> None:
        pass  # Moodle 3.9 no acepta enrolment_1 como parametro de core_course_create_courses

        # ---------------------------------------------------------------------------
        # Fábrica de adaptadores
        # ---------------------------------------------------------------------------


class FabricaAdaptadorMoodle:
    """
    Crea el adaptador correspondiente según la versión de Moodle.
    """

    _adapters: ClassVar[dict[str, type]] = {
        "3.8": AdaptadorMoodle3,
        "3.9": AdaptadorMoodle3,
        "4.0": AdaptadorMoodle3,
        "4.1": AdaptadorMoodle3,
        "4.2": AdaptadorMoodle3,
        "4.3": AdaptadorMoodle3,
        "4.4": AdaptadorMoodle3,
        "4.5": AdaptadorMoodle3,
    }
    # NOTA: Las versiones 4.x se mapean a Moodle3Adapter por compatibilidad observada.
    # Si Moodle 4.x introduce cambios en core_course_get_courses_by_field,
    # core_enrol_get_course_enrolment_methods o core_course_create_courses,
    # se debe crear Moodle4Adapter y actualizar este mapeo.

    @classmethod
    def crear(cls, version: str) -> AdaptadorMoodle:
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
