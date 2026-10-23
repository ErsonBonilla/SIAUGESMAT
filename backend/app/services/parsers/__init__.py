from app.services.parsers.distancia import AnalizadorDistancia
from app.services.parsers.fabrica import FabricaAnalizadores

FabricaAnalizadores.register("DISTANCIA", AnalizadorDistancia)

__all__ = ["AnalizadorDistancia", "FabricaAnalizadores"]
