from app.services.parsers.distancia import DistanciaParser
from app.services.parsers.factory import ParserFactory

ParserFactory.register("DISTANCIA", DistanciaParser)

__all__ = ["DistanciaParser", "ParserFactory"]
