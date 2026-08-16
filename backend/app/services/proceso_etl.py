"""
Servicio ETL: extracción y transformación de datos desde el archivo Excel.

Convierte las hojas de carga académica en estructuras de datos listas
para ser enviadas a Moodle (categorías, cursos, usuarios, matriculaciones)
siguiendo las reglas definidas por la Universidad del Tolima.
"""

from typing import Any

from app.services.parsers.fabrica import FabricaAnalizadores


class ServicioETL:
    """Fachada que orquesta la lectura y parseo del Excel según la modalidad."""

    @staticmethod
    def procesar(file_path: str, modalidad: str) -> dict[str, Any]:
        parser_cls = FabricaAnalizadores.obtener_analizador(modalidad)
        df = parser_cls.leer_excel(file_path)
        return parser_cls.parsear(df, modalidad)
