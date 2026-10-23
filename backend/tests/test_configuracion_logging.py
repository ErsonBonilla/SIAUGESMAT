"""
Pruebas del formateador JSON de logs.

Verifica que `FormateadorJSON` inyecte los campos `level` y `logger` en cada
registro. Regresión del bug en que el método de override se llamó `agregar_campos`
en vez del hook real `add_fields` de `pythonjsonlogger.JsonFormatter`, dejando
`level` en null y `logger` ausente en los logs JSON de producción.
"""

import json
import logging

from app.core.configuracion_logging import FormateadorJSON, configurar_logging


def test_formatea_level_y_logger():
    registro = logging.LogRecord("app.ejemplo", logging.INFO, "modulo.py", 1, "hola", (), None)
    salida = FormateadorJSON().format(registro)
    datos = json.loads(salida)
    assert datos["level"] == "INFO"
    assert datos["logger"] == "app.ejemplo"
    assert datos["message"] == "hola"


def test_formatea_level_error():
    registro = logging.LogRecord("app.ejemplo", logging.ERROR, "modulo.py", 1, "boom", (), None)
    datos = json.loads(FormateadorJSON().format(registro))
    assert datos["level"] == "ERROR"


def test_configurar_logging_json_por_defecto():
    configurar_logging(debug=False)
    root = logging.getLogger()
    try:
        assert root.handlers
        formatter = root.handlers[0].formatter
        assert isinstance(formatter, FormateadorJSON)
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
