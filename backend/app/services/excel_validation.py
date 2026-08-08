"""
Validación de contenido de archivos Excel según su formato real.

Detecta si los bytes de un archivo corresponden a un formato de hoja de
cálculo soportado por el pipeline (BIFF/.xls o ZIP con hojas OOXML/ODF)
usando magic bytes, sin depender únicamente de la extensión.
"""

import zipfile
from io import BytesIO

_OLE2_CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def is_excel_content(data: bytes) -> bool:
    """Devuelve True si los bytes parecen un archivo Excel legible.

    Replica la detección automática del motor calamine: acepta libros
    binarios (BIFF/.xls) y archivos ZIP que contengan '[Content_Types].xml'
    (xlsx, xlsm, xlsb, ods).
    """
    if data[:8] == _OLE2_CFB_MAGIC:
        return True

    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            return any(name.lower() == "[content_types].xml" for name in archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return False
