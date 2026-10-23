from typing import ClassVar

from app.services.parsers.base import AnalizadorExcelBase


class FabricaAnalizadores:
    _registry: ClassVar[dict] = {}

    @classmethod
    def register(cls, modalidad: str, parser_cls):
        cls._registry[modalidad.upper()] = parser_cls

    @classmethod
    def obtener_analizador(cls, modalidad: str) -> AnalizadorExcelBase:
        modalidad_upper = modalidad.upper()
        parser_cls = cls._registry.get(modalidad_upper)
        if not parser_cls:
            raise ValueError(
                f"Modalidad desconocida: '{modalidad}'. "
                f"Modalidades soportadas: {list(cls._registry.keys())}"
            )
        return parser_cls
