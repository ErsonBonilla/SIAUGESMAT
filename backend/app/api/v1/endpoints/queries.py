"""
Endpoints de consulta asíncrona a Moodle.
"""

import csv
import io
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.repositories.query_repo import (
    create_query,
    get_query,
)
from app.schemas.user import UserInToken
from app.workers.query_tasks import execute_query

logger = logging.getLogger(__name__)

router = APIRouter()

ENTITY_LABELS = {
    "courses": "Cursos",
    "categories": "Categorías",
    "users": "Usuarios",
    "inactive_teachers": "Docentes sin acceso",
}

ENTITY_CSV_HEADERS = {
    "courses": ["ID", "Shortname", "Nombre", "Categoría", "Visible", "Creado"],
    "categories": ["ID", "Nombre", "ID Number", "Padre", "Cursos", "Descripción"],
    "users": ["Username", "Email", "Nombres", "Apellidos", "Último login"],
    "inactive_teachers": [
        "Docente", "Username", "Correo", "Curso", "Shortname",
        "Programa", "CAT", "Último acceso",
    ],
}

ENTITY_CSV_EXTRACT = {
    "courses": lambda c: [
        c.get("id", ""), c.get("shortname", ""), c.get("fullname", ""),
        c.get("categoryname", ""),
        "Sí" if c.get("visible", 1) == 1 else "No",
        c.get("timecreated", ""),
    ],
    "categories": lambda c: [
        c.get("id", ""), c.get("name", ""), c.get("idnumber", ""),
        c.get("parent", ""), c.get("coursecount", ""), c.get("description", ""),
    ],
    "users": lambda u: [
        u.get("username", ""), u.get("email", ""),
        u.get("firstname", ""), u.get("lastname", ""),
        "Nunca" if u.get("lastlogin", 0) == 0 else str(u.get("lastlogin", "")),
    ],
    "inactive_teachers": lambda r: [
        r.get("teacher_name", ""), r.get("username", ""), r.get("email", ""),
        r.get("course_name", ""), r.get("course_shortname", ""),
        r.get("program", ""), r.get("cat", ""),
        "Nunca" if r.get("last_access", 0) == 0
        else datetime.fromtimestamp(r["last_access"]).strftime("%Y-%m-%d %H:%M"),
    ],
}


def _csv_download(qr):
    entity = qr.entity
    headers = ENTITY_CSV_HEADERS.get(entity, ["data"])
    extract = ENTITY_CSV_EXTRACT.get(entity, lambda x: [str(x)])
    data = qr.result_json or []

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in data:
        writer.writerow(extract(row))
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename={entity}_consulta_{qr.task_id[:8]}.csv"
        },
    )


@router.post("/{entity}", summary="Encolar consulta asíncrona")
async def enqueue_query(
    entity: str,
    body: dict = Body(default={}),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    if entity not in ENTITY_LABELS:
        raise HTTPException(400, f"Entidad desconocida: {entity}")

    task_id = str(uuid.uuid4())
    create_query(db, task_id, entity, body, current_user.modalidad)
    execute_query.delay(task_id)

    label = ENTITY_LABELS[entity].lower()
    logger.info(f"Consulta de {label} encolada (task={task_id[:8]}) por {current_user.username}")

    return {
        "task_id": task_id, "entity": entity, "status": "pending",
        "message": f"Consulta de {label} encolada. Esperando resultado...",
    }


@router.get("/tasks/{task_id}", summary="Consultar estado de una consulta")
def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    qr = get_query(db, task_id)
    if not qr:
        raise HTTPException(404, "Tarea de consulta no encontrada")

    response = {
        "task_id": qr.task_id, "entity": qr.entity,
        "status": qr.status, "total_count": qr.total_count,
    }
    if qr.status == "completed":
        response["result"] = qr.result_json
    elif qr.status == "failed":
        response["error"] = qr.error_message
    return response


@router.get("/tasks/{task_id}/download", summary="Descargar resultado como CSV")
def download_task_csv(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    qr = get_query(db, task_id)
    if not qr:
        raise HTTPException(404, "Tarea de consulta no encontrada")
    if qr.status != "completed":
        raise HTTPException(409, "La consulta aún no ha finalizado")
    return _csv_download(qr)
