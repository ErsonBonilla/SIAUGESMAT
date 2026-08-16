from abc import ABC, abstractmethod
from typing import Any

from app.integrations.integracion_moodle import IntegracionMoodle
from app.services.errores_moodle import ErrorMoodleSobrecargado as ErrorMoodleSobrecargado
from app.services.operaciones_moodle import ServicioMoodle

__all__ = ["ContextoFase", "ErrorMoodleSobrecargado"]


class ContextoFase:
    def __init__(
        self,
        db,
        ejecucion_id: int,
        ejecucion,
        modo: str,
        semestre: str,
        datos_etl: dict[str, Any],
        servicio_moodle: ServicioMoodle,
        integracion: IntegracionMoodle,
    ):
        self.db = db
        self.ejecucion_id = ejecucion_id
        self.ejecucion = ejecucion
        self.modo = modo
        self.semestre = semestre
        self.datos_etl = datos_etl
        self.servicio_moodle = servicio_moodle
        self.integracion = integracion

        self.idnumeros_categorias_existentes: set[str] = set()
        self.mapa_todas_categorias: dict[str, dict] = {}
        self.cursos_existentes: list[dict] = []
        self.mapa_usuarios: dict[str, str] = {}
        self.correos_usuarios: dict[str, str] = {}
        self.cursos_con_docente: dict[str, str] = {}
        self.mapa_curso_docente: dict[str, str] = {}

        self.nueva_subida: bool = False
        self.categorias_faltantes: list[dict] = []
        self.categorias_a_reubicar: list[dict] = []
        self.comparacion: dict[str, Any] = {}
        self.usuarios_a_crear: list[dict] = []
        self.matriculas_resueltas: list[dict] = []

        self.progreso_estructura: dict[str, Any] = {}
        self.progreso_personas: dict[str, Any] = {}

        self.metricas: dict[str, int] = {
            "categories_created": 0,
            "courses_created": 0,
            "courses_deleted": 0,
            "courses_activated": 0,
            "courses_hidden": 0,
            "users_created": 0,
            "enrolments": 0,
            "enrolment_errors": 0,
            "alerts": 0,
            "total_errors": 0,
        }


class FaseBase(ABC):
    phase_name: str = ""

    @abstractmethod
    async def ejecutar(self, ctx: ContextoFase) -> None: ...
