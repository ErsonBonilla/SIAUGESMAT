from app.services.parsers.factory import ParserFactory
from app.services.parsers.distancia import DistanciaParser

ParserFactory.register("DISTANCIA", DistanciaParser)

__all__ = ["ParserFactory", "DistanciaParser"]
