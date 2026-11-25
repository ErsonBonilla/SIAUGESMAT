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
    obtener_estado_observatorio,
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
    "observatorio": "Observatorio IDEAD Colombia",
}

ENTITY_CSV_HEADERS = {
    "courses": ["ID", "Shortname", "Nombre", "Categoría", "Visible", "Creado"],
    "categories": ["ID", "Nombre", "ID Number", "Padre", "Cursos", "Descripción"],
    "users": ["Username", "Email", "Nombres", "Apellidos", "Último acceso"],
    "inactive_teachers": [
        "Shortname CAT",
        "Nombre CAT",
        "Shortname Semestre",
        "Nombre Semestre",
        "Shortname Programa",
        "Nombre Programa",
        "Shortname Curso",
        "Curso",
        "Username",
        "Docente",
        "Correo",
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
    "observatorio": [
        "Código Depto",
        "Departamento",
        "Código Municipio",
        "Municipio (CAT)",
        "Shortname CAT",
        "Código Programa",
        "Programa",
        "Cursos Activos",
        "Estudiantes Matriculados",
    ],
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
        r.get("cat_shortname", ""),
        r.get("cat_name", r.get("cat", "")),
        r.get("semester_shortname", ""),
        r.get("semester_name", ""),
        r.get("program_shortname", r.get("program", "")),
        r.get("program_name", ""),
        r.get("course_shortname", ""),
        r.get("course_name", ""),
        r.get("username", ""),
        r.get("teacher_name", ""),
        r.get("email", ""),
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
    "observatorio": lambda r: [
        r.get("dpto_code", ""),
        r.get("dpto_name", ""),
        r.get("mpio_code", ""),
        r.get("display_name", ""),
        r.get("cat_shortname", ""),
        r.get("program_code", ""),
        r.get("program_name", ""),
        r.get("courses_count", 0),
        r.get("students_count", 0),
    ],
}


def _aplanar_censo_observatorio(censo: dict) -> list[dict]:
    filas: list[dict] = []
    for dpto in censo.get("departments", []):
        for mpio in dpto.get("municipalities", []):
            for prog in mpio.get("programs", []):
                filas.append(
                    {
                        "dpto_code": dpto.get("dpto_code", ""),
                        "dpto_name": dpto.get("dpto_name", ""),
                        "mpio_code": mpio.get("mpio_code", ""),
                        "display_name": mpio.get("display_name", mpio.get("mpio_name", "")),
                        "cat_shortname": mpio.get("cat_shortname", ""),
                        "program_code": prog.get("program_code", ""),
                        "program_name": prog.get("program_name", ""),
                        "courses_count": prog.get("courses_count", 0),
                        "students_count": prog.get("students_count", 0),
                    }
                )
    return filas


def _descargar_csv(qr):
    entidad = qr.entidad
    headers = ENTITY_CSV_HEADERS.get(entidad, ["data"])
    extract = ENTITY_CSV_EXTRACT.get(entidad, lambda x: [str(x)])
    raw_data = qr.resultado_json or []
    data = (
        _aplanar_censo_observatorio(raw_data)
        if entidad == "observatorio" and isinstance(raw_data, dict)
        else raw_data
    )

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


@router.get("/observatorio/latest", summary="Obtener último censo del Observatorio IDEAD")
def obtener_ultimo_censo_observatorio(
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    completada, activa = obtener_estado_observatorio(db, usuario_actual.modalidad)
    if not completada and not activa:
        return {
            "task_id": None,
            "active_task_id": None,
            "status": "empty",
            "updated_at": None,
            "result": None,
        }
    return {
        "task_id": completada.id_tarea if completada else (activa.id_tarea if activa else None),
        "active_task_id": activa.id_tarea if activa else None,
        "status": "completed" if completada else (activa.estado if activa else "empty"),
        "updated_at": (
            completada.completado_en.isoformat()
            if completada and completada.completado_en
            else None
        ),
        "result": completada.resultado_json if completada else None,
    }


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

    if entidad == "observatorio":
        _, activa = obtener_estado_observatorio(db, usuario_actual.modalidad)
        if activa:
            return {
                "task_id": activa.id_tarea,
                "entity": entidad,
                "status": activa.estado,
                "message": "Actualización del Observatorio en curso...",
            }

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
    if not qr or (qr.modalidad and qr.modalidad != usuario_actual.modalidad):
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
    if not qr or (qr.modalidad and qr.modalidad != usuario_actual.modalidad):
        raise HTTPException(404, "Tarea de consulta no encontrada")
    if qr.estado != "completed":
        raise HTTPException(409, "La consulta aún no ha finalizado")
    return _descargar_csv(qr)
