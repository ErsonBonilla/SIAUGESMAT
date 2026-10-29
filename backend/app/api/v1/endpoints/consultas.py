"""
Endpoints de consulta asíncrona a Moodle.
"""

import csv
import io
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.repositories.repositorio_consultas import (
    crear_consulta,
    obtener_consulta,
)
from app.schemas.respuestas import RespuestaConsultaEncolada
from app.schemas.usuario import UsuarioEnToken
from app.services.orquestacion import encolar_consulta_async

logger = logging.getLogger(__name__)

router = APIRouter()

ENTITY_LABELS = {
    "courses": "Cursos",
    "categories": "Categorías",
    "users": "Usuarios",
    "inactive_teachers": "Docentes sin acceso",
    "inactive_courses": "Cursos sin uso",
    "duplicate_emails": "Correos duplicados",
}

ENTITY_CSV_HEADERS = {
    "courses": ["ID", "Shortname", "Nombre", "Categoría", "Visible", "Creado"],
    "categories": ["ID", "Nombre", "ID Number", "Padre", "Cursos", "Descripción"],
    "users": ["Username", "Email", "Nombres", "Apellidos", "Último acceso"],
    "inactive_teachers": [
        "Docente",
        "Username",
        "Correo",
        "Curso",
        "Shortname",
        "Programa",
        "CAT",
        "Último acceso",
        "Días sin acceso",
    ],
    "inactive_courses": [
        "ID",
        "Shortname",
        "Nombre",
        "Categoría",
        "Programa",
        "CAT",
        "Última modificación",
        "Días sin uso",
    ],
    "duplicate_emails": ["Email", "Username", "Nombres", "Apellidos", "ID Moodle", "Nº de cuentas"],
}

ENTITY_CSV_EXTRACT = {
    "courses": lambda c: [
        c.get("id", ""),
        c.get("shortname", ""),
        c.get("fullname", ""),
        c.get("categoryname", ""),
        "Sí" if c.get("visible", 1) == 1 else "No",
        c.get("timecreated", ""),
    ],
    "categories": lambda c: [
        c.get("id", ""),
        c.get("name", ""),
        c.get("idnumber", ""),
        c.get("parent", ""),
        c.get("coursecount", ""),
        c.get("description", ""),
    ],
    "users": lambda u: [
        u.get("username", ""),
        u.get("email", ""),
        u.get("firstname", ""),
        u.get("lastname", ""),
        "Nunca" if u.get("lastlogin", 0) == 0 else str(u.get("lastlogin", "")),
    ],
    "inactive_teachers": lambda r: [
        r.get("teacher_name", ""),
        r.get("username", ""),
        r.get("email", ""),
        r.get("course_name", ""),
        r.get("course_shortname", ""),
        r.get("program", ""),
        r.get("cat", ""),
        "Nunca"
        if r.get("last_access", 0) == 0
        else datetime.fromtimestamp(r["last_access"], tz=UTC).strftime("%Y-%m-%d %H:%M"),
        "Nunca" if r.get("last_access", 0) == 0 else str(r.get("days_since_last_access", "")),
    ],
    "inactive_courses": lambda c: [
        c.get("id", ""),
        c.get("shortname", ""),
        c.get("fullname", ""),
        c.get("categoryname", ""),
        c.get("program", ""),
        c.get("cat", ""),
        "Nunca"
        if not c.get("timemodified")
        else datetime.fromtimestamp(c["timemodified"], tz=UTC).strftime("%Y-%m-%d %H:%M"),
        "Nunca" if not c.get("timemodified") else str(c.get("days_since_modified", "")),
    ],
    "duplicate_emails": lambda r: [
        r.get("email", ""),
        r.get("username", ""),
        r.get("firstname", ""),
        r.get("lastname", ""),
        r.get("user_id", ""),
        r.get("duplicate_count", ""),
    ],
}


def _descargar_csv(qr):
    entidad = qr.entidad
    headers = ENTITY_CSV_HEADERS.get(entidad, ["data"])
    extract = ENTITY_CSV_EXTRACT.get(entidad, lambda x: [str(x)])
    data = qr.resultado_json or []

    def _generar():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        yield buffer.getvalue().encode("utf-8-sig")
        for row in data:
            buffer.seek(0)
            buffer.truncate()
            writer.writerow(extract(row))
            yield buffer.getvalue().encode("utf-8")

    return StreamingResponse(
        _generar(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={entidad}_consulta_{qr.id_tarea[:8]}.csv"
        },
    )


@router.post(
    "/{entidad}", response_model=RespuestaConsultaEncolada, summary="Encolar consulta asíncrona"
)
async def encolar_consulta(
    entidad: str,
    body: dict | None = Body(default=None),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    if entidad not in ENTITY_LABELS:
        raise HTTPException(400, f"Entidad desconocida: {entidad}")

    id_tarea = str(uuid.uuid4())
    crear_consulta(db, id_tarea, entidad, body or {}, usuario_actual.modalidad)
    encolar_consulta_async(id_tarea)

    label = ENTITY_LABELS[entidad].lower()
    logger.info(f"Consulta de {label} encolada (task={id_tarea[:8]}) por {usuario_actual.username}")

    return {
        "task_id": id_tarea,
        "entity": entidad,
        "status": "pending",
        "message": f"Consulta de {label} encolada. Esperando resultado...",
    }


@router.get("/tasks/{id_tarea}", summary="Consultar estado de una consulta")
def obtener_estado_tarea(
    id_tarea: str,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    qr = obtener_consulta(db, id_tarea)
    if not qr:
        raise HTTPException(404, "Tarea de consulta no encontrada")

    response = {
        "task_id": qr.id_tarea,
        "entity": qr.entidad,
        "status": qr.estado,
        "total_count": qr.conteo_total,
    }
    if qr.estado == "completed":
        response["result"] = qr.resultado_json
    elif qr.estado == "failed":
        response["error"] = qr.mensaje_error
    return response


@router.get("/tasks/{id_tarea}/download", summary="Descargar resultado como CSV")
def descargar_csv_tarea(
    id_tarea: str,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    qr = obtener_consulta(db, id_tarea)
    if not qr:
        raise HTTPException(404, "Tarea de consulta no encontrada")
    if qr.estado != "completed":
        raise HTTPException(409, "La consulta aún no ha finalizado")
    return _descargar_csv(qr)
