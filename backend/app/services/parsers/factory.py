from app.services.parsers.base import BaseExcelParser


class ParserFactory:
    _registry = {}

    @classmethod
    def register(cls, modalidad: str, parser_cls):
        cls._registry[modalidad.upper()] = parser_cls

    @classmethod
    def get_parser(cls, modalidad: str) -> BaseExcelParser:
        modalidad_upper = modalidad.upper()
        parser_cls = cls._registry.get(modalidad_upper)
        if not parser_cls:
            raise ValueError(
                f"Modalidad desconocida: '{modalidad}'. "
                f"Modalidades soportadas: {list(cls._registry.keys())}"
            )
        return parser_cls
