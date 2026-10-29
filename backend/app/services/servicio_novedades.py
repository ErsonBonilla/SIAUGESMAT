import asyncio
import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.modelos import Ejecucion
from app.pipeline.novedades import detectar_novedades
from app.services.proceso_etl import ServicioETL

logger = logging.getLogger(__name__)


async def detectar(
    db: Session,
    semester: str,
    modalidad: str,
    new_file_path: str,
) -> tuple[dict[str, Any], str | None]:
    new_data = await asyncio.to_thread(ServicioETL.procesar, new_file_path, modalidad)
    new_courses = new_data.get("courses", [])

    if not new_courses:
        return {}, "El archivo nuevo no contiene cursos."

    previous = (
        db.query(Ejecucion)
        .filter(
            Ejecucion.semestre == semester,
            Ejecucion.modalidad == modalidad,
            Ejecucion.estado == "completed",
        )
        .order_by(Ejecucion.creado_en.desc())
        .first()
    )
    if not previous:
        return {}, f"No se encontró una ejecución previa completada para el semestre {semester}."

    old_file_path = os.path.join(settings.UPLOAD_DIR, previous.nombre_archivo)
    if not os.path.exists(old_file_path):
        return (
            {},
            f"El archivo de la ejecución anterior ({previous.nombre_archivo}) ya no existe en el servidor.",
        )

    old_data = await asyncio.to_thread(ServicioETL.procesar, old_file_path, modalidad)

    novedades, stats = detectar_novedades(old_data, new_data)

    return {
        "semester": semester,
        "previous_execution_id": previous.id,
        "previous_filename": previous.nombre_archivo,
        "total_compared": stats["total_compared"],
        "novedades": novedades,
    }, None
