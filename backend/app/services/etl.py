"""
Servicio ETL: extracción y transformación de datos desde el archivo Excel.

Convierte las hojas de carga académica en estructuras de datos listas
para ser enviadas a Moodle (categorías, cursos, usuarios, matriculaciones)
siguiendo las reglas definidas por la Universidad del Tolima.
"""

import logging
from typing import Any, Dict

from app.services.parsers.factory import ParserFactory
from app.services.error_messages import translate_error

logger = logging.getLogger(__name__)


class ETLService:
    """Fachada que orquesta la lectura y parseo del Excel según la modalidad."""

    @staticmethod
    def process(file_path: str, modalidad: str) -> Dict[str, Any]:
        try:
            parser_cls = ParserFactory.get_parser(modalidad)
            df = parser_cls.read_excel(file_path)
            return parser_cls.parse(df, modalidad)
        except Exception as e:
            logger.exception(f"Error procesando archivo ETL {file_path}: {translate_error(e)}")
            raise
