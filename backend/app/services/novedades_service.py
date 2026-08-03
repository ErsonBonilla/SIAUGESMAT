import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Execution
from app.pipeline.novedades import detect_novedades
from app.services.etl import ETLService

logger = logging.getLogger(__name__)


async def detect(
    db: Session,
    semester: str,
    modalidad: str,
    new_file_path: str,
) -> tuple[dict[str, Any], str | None]:
    new_data = ETLService.process(new_file_path, modalidad)
    new_courses = new_data.get("courses", [])

    if not new_courses:
        return {}, "El archivo nuevo no contiene cursos."

    previous = (
        db.query(Execution)
        .filter(
            Execution.semester == semester,
            Execution.modalidad == modalidad,
            Execution.status == "completed",
        )
        .order_by(Execution.created_at.desc())
        .first()
    )
    if not previous:
        return {}, f"No se encontró una ejecución previa completada para el semestre {semester}."

    old_file_path = os.path.join(settings.UPLOAD_DIR, previous.filename)
    if not os.path.exists(old_file_path):
        return {}, f"El archivo de la ejecución anterior ({previous.filename}) ya no existe en el servidor."

    old_data = ETLService.process(old_file_path, modalidad)

    novedades, stats = detect_novedades(old_data, new_data)

    return {
        "semester": semester,
        "previous_execution_id": previous.id,
        "previous_filename": previous.filename,
        "total_compared": stats["total_compared"],
        "novedades": novedades,
    }, None
