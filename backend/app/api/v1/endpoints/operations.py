"""
Endpoints de operaciones masivas (creación y eliminación) de entidades en Moodle.
"""

import csv
import io
import logging
import os
import tempfile
import uuid
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.repositories.operation_repo import (
    add_item,
    create_batch,
    delete_old_batches,
    get_all_batch_items,
    get_batch,
    get_batch_items,
    get_batch_status,
    get_operations_analytics,
    list_batches,
)
from app.schemas.operations import (
    BatchListResponse,
    BatchStatusResponse,
    CsvUploadResponse,
    DeleteOldBatchesResponse,
    OperationItemOut,
    OperationsAnalyticsResponse,
)
from app.schemas.user import UserInToken
from app.services.moodle_adapter import resolve_role
from app.workers.operations_tasks import process_operation_batch

logger = logging.getLogger(__name__)

router = APIRouter()

ENTITY_CONFIG = {
    "courses": {"column": "shortname", "label": "curso", "label_plural": "cursos"},
    "categories": {"column": "idnumber", "label": "categoría", "label_plural": "categorías"},
    "users": {"column": "username", "label": "usuario", "label_plural": "usuarios"},
}


def _validate_and_parse_csv(content: str, column: str, label_plural: str) -> list[str]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("El archivo CSV está vacío o no tiene cabecera")

    fieldnames = [name.strip().lower() for name in reader.fieldnames]
    if column not in fieldnames:
        raise ValueError(f"Falta la columna requerida: '{column}'")

    actual = next((n for n in reader.fieldnames if n.strip().lower() == column), column)
    values = []
    for row_num, row in enumerate(reader, start=2):
        value = row.get(actual, "").strip()
        if not value:
            raise ValueError(f"Fila {row_num}: '{column}' vacío")
        values.append(value)

    if not values:
        raise ValueError(f"No se encontraron {label_plural} en el archivo CSV.")
    return values


def _validate_users_csv(content: str, default_role: str = None) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("El archivo CSV está vacío o no tiene cabecera")

    required = {"username", "firstname", "lastname", "email"}
    fieldnames = [n.strip().lower() for n in reader.fieldnames]
    missing = required - set(fieldnames)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(sorted(missing))}")

    has_role_column = "role1" in {n.strip().lower() for n in reader.fieldnames}
    if not default_role and not has_role_column:
        raise ValueError(
            "Debe incluir la columna 'role1' o especificar un default_role"
        )

    users = []
    for row_num, row in enumerate(reader, start=2):
        user = {}
        for col in required:
            actual = next((n for n in reader.fieldnames if n.strip().lower() == col), col)
            value = row.get(actual, "").strip()
            if not value:
                raise ValueError(f"Fila {row_num}: '{col}' vacío")
            user[col] = value

        password = (row.get("password") or "").strip()
        if password:
            user["password"] = password

        user["role1"] = default_role
        if has_role_column:
            role_actual = next((n for n in reader.fieldnames if n.strip().lower() == "role1"), "role1")
            csv_role = (row.get(role_actual) or "").strip()
            if csv_role:
                try:
                    resolve_role(csv_role)
                except (ValueError, KeyError):
                    raise ValueError(f"Fila {row_num}: rol inválido '{csv_role}'")
                user["role1"] = csv_role

        fpc_field = next((n for n in reader.fieldnames if n.strip().lower() == "forcepasswordchange"), None)
        if fpc_field:
            fpc = (row.get(fpc_field) or "").strip()
            if fpc in ("1", "0"):
                user["forcepasswordchange"] = fpc

        users.append(user)

    if not users:
        raise ValueError("No se encontraron usuarios en el archivo CSV.")
    return users


def _get_field(row: dict, fieldnames: list, column: str, required: bool = False, row_num: int = 0) -> str:
    actual = next((n for n in fieldnames if n.strip().lower() == column), column)
    value = (row.get(actual) or "").strip()
    if required and not value:
        raise ValueError(f"Fila {row_num}: '{column}' vacío")
    return value


def _validate_categories_csv(content: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("El archivo CSV está vacío o no tiene cabecera")

    fieldnames = [n.strip().lower() for n in reader.fieldnames]
    if "name" not in fieldnames:
        raise ValueError("Falta la columna requerida: 'name'")

    categories = []
    for row_num, row in enumerate(reader, start=2):
        name = _get_field(row, reader.fieldnames, "name", required=True, row_num=row_num)
        cat = {"name": name}
        idnumber = _get_field(row, reader.fieldnames, "idnumber")
        if idnumber:
            cat["idnumber"] = idnumber
        parent = _get_field(row, reader.fieldnames, "parent")
        cat["parent"] = parent
        description = _get_field(row, reader.fieldnames, "description")
        if description:
            cat["description"] = description
        visible = _get_field(row, reader.fieldnames, "visible")
        if visible in ("0", "1"):
            cat["visible"] = int(visible)
        categories.append(cat)

    if not categories:
        raise ValueError("No se encontraron categorías en el archivo CSV.")
    return _sort_categories(categories)


def _sort_categories(categories: list[dict]) -> list[dict]:
    sorted_cats = []
    roots = [c for c in categories if not c.get("parent")]
    for root in roots:
        sorted_cats.append(root)
        root_id = root.get("idnumber") or root["name"]
        hijos_n1 = [c for c in categories if c.get("parent") == root_id]
        for h1 in hijos_n1:
            sorted_cats.append(h1)
            h1_id = h1.get("idnumber") or h1["name"]
            hijos_n2 = [c for c in categories if c.get("parent") == h1_id]
            for h2 in hijos_n2:
                sorted_cats.append(h2)
                h2_id = h2.get("idnumber") or h2["name"]
                hijos_n3 = [c for c in categories if c.get("parent") == h2_id]
                sorted_cats.extend(hijos_n3)
    orphans = [c for c in categories if c not in sorted_cats]
    sorted_cats.extend(orphans)
    return sorted_cats


@router.post("/courses/upload-csv", response_model=CsvUploadResponse, summary="Eliminar cursos masivamente")
async def delete_courses_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await _handle_upload(file, db, current_user, entity_type="courses", action="delete")


@router.post("/categories/upload-csv", response_model=CsvUploadResponse, summary="Eliminar categorías masivamente")
async def delete_categories_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await _handle_upload(file, db, current_user, entity_type="categories", action="delete")


@router.post("/users/upload-csv", response_model=CsvUploadResponse, summary="Eliminar usuarios masivamente")
async def delete_users_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await _handle_upload(file, db, current_user, entity_type="users", action="delete")


@router.post("/courses/visibility", response_model=CsvUploadResponse,
             summary="Cambiar visibilidad de cursos masivamente")
async def bulk_course_visibility(
    file: UploadFile = File(...),
    visibility: str = Query("show", regex="^(show|hide)$"),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await _handle_visibility_upload(file, db, current_user, visibility)


@router.post("/users/create-csv", response_model=CsvUploadResponse, summary="Crear usuarios masivamente")
async def create_users_csv(
    file: UploadFile = File(...),
    default_role: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await _handle_upload(file, db, current_user, entity_type="users", action="create",
                                default_role=default_role)


@router.post("/categories/create-csv", response_model=CsvUploadResponse, summary="Crear categorías masivamente")
async def create_categories_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await _handle_upload(file, db, current_user, entity_type="categories", action="create")


@router.get("/batch/{batch_id}/status", response_model=BatchStatusResponse,
            summary="Consultar estado de un lote de operaciones")
def get_batch_status_endpoint(
    batch_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db), current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    status = get_batch_status(db, batch_id)
    items = get_batch_items(db, batch_id, offset, limit)

    return BatchStatusResponse(
        batch_id=batch.batch_id, entity_type=batch.entity_type, action=batch.action,
        total=status["total"], pending=status["pending"], processing=status["processing"],
        completed=status["completed"], failed=status["failed"],
        offset=offset, limit=limit,
        details=[OperationItemOut(
            identifier=i.identifier, status=i.status,
            error_message=i.error_message, attempt=i.attempt,
        ) for i in items],
    )


@router.get("/batch/{batch_id}/reports/download",
            summary="Descargar reportes (ZIP con CSVs)")
def download_batch_reports(
    batch_id: str, background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), current_user: UserInToken = Depends(get_current_user),
):
    batch = get_batch(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")

    items = get_all_batch_items(db, batch_id)
    config = ENTITY_CONFIG.get(batch.entity_type, ENTITY_CONFIG["courses"])

    all_rows, failed_rows, success_rows, not_found_rows = [], [], [], []
    for item in items:
        det = item.detail or {}
        row = {
            "identificador": item.identifier, "estado": item.status,
            "error": item.error_message or "", "intentos": str(item.attempt or 0),
        }
        if batch.entity_type == "categories" and batch.action == "create":
            row["idnumber"] = det.get("idnumber") or ""
            row["parent"] = det.get("parent") or "DISTANCIA"
            row["description"] = det.get("description") or ""
            row["visible"] = str(det.get("visible", 1))
        if batch.entity_type == "users" and batch.action == "create":
            row["firstname"] = det.get("firstname") or ""
            row["lastname"] = det.get("lastname") or ""
            row["email"] = det.get("email") or ""
            row["rol"] = det.get("role1") or ""
        all_rows.append(row)

        if item.status == "failed":
            failed_rows.append(row)
            if batch.action == "delete" and item.error_message:
                msg_lower = item.error_message.lower()
                if any(w in msg_lower for w in ("no encontrad", "not found", "notfound")):
                    not_found_rows.append(row)
        if item.status == "completed":
            success_rows.append(row)

    action_verb = "Eliminación" if batch.action == "delete" else "Creación"
    base_headers = ["identificador", "estado", "error", "intentos"]
    if batch.entity_type == "categories" and batch.action == "create":
        base_headers += ["idnumber", "parent", "description", "visible"]
    elif batch.entity_type == "users" and batch.action == "create":
        base_headers += ["firstname", "lastname", "email", "rol"]

    csv_files = [
        ("resultados.csv", base_headers, all_rows),
        ("fallidos.csv", base_headers, failed_rows),
    ]
    if batch.action == "create":
        csv_files.append(("creados.csv", base_headers, success_rows))
    if batch.action == "delete" and not_found_rows:
        csv_files.append(("no_encontrados.csv",
                          ["identificador", "estado", "error", "intentos"],
                          not_found_rows))

    total = len(items)
    completed = sum(1 for i in items if i.status == "completed")
    failed = sum(1 for i in items if i.status == "failed")
    resumen_rows = [
        {"campo": "Tipo de entidad", "valor": config["label_plural"]},
        {"campo": "Operación", "valor": action_verb},
        {"campo": "Total", "valor": str(total)},
        {"campo": "Completados", "valor": str(completed)},
        {"campo": "Fallidos", "valor": str(failed)},
        {"campo": "Batch ID", "valor": batch_id},
        {"campo": "Creado", "valor": batch.created_at.isoformat() if batch.created_at else ""},
        {"campo": "Completado", "valor": batch.completed_at.isoformat() if batch.completed_at else ""},
    ]
    csv_files.append(("resumen.csv", ["campo", "valor"], resumen_rows))

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        zip_path = tmp.name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, headers, rows in csv_files:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(headers)
            if rows and isinstance(rows[0], dict):
                for r in rows:
                    writer.writerow([r.get(h, "") for h in headers])
            buf.seek(0)
            zf.writestr(filename, buf.getvalue().encode("utf-8-sig"))

    zip_filename = f"reportes_{batch.action}_{batch.entity_type}_{batch_id[:8]}.zip"
    background_tasks.add_task(os.unlink, zip_path)
    return FileResponse(path=zip_path, media_type="application/zip", filename=zip_filename)


@router.delete("/batches/old", response_model=DeleteOldBatchesResponse,
               summary="Eliminar lotes antiguos")
def delete_old(
    days: int = Query(30, ge=1), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    deleted = delete_old_batches(db, days)
    return DeleteOldBatchesResponse(deleted_batches=deleted, older_than_days=days)


@router.get("/batches", response_model=BatchListResponse,
            summary="Listar lotes de operaciones")
def list_operation_batches(
    entity_type: str | None = Query(None, description="courses, categories, users"),
    action: str | None = Query(None, description="create, delete"),
    modalidad: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    total, batches = list_batches(
        db, entity_type=entity_type, action=action,
        modalidad=modalidad, limit=limit, offset=offset,
    )
    from app.schemas.operations import BatchListOut
    return BatchListResponse(
        total=total,
        items=[BatchListOut.model_validate(b) for b in batches],
    )


@router.get("/analytics", response_model=OperationsAnalyticsResponse,
            summary="Analítica histórica de operaciones masivas")
def get_operations_history(
    modalidad: str | None = Query(None),
    months: int = Query(12, ge=1, le=60),
    entity_type: str | None = Query(None, description="courses, categories, users"),
    action: str | None = Query(None, description="create, delete"),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    history = get_operations_analytics(
        db, modalidad=modalidad, months=months,
        entity_type=entity_type, action=action,
    )
    from app.schemas.operations import OperationMonthlyMetrics
    return OperationsAnalyticsResponse(
        history=[OperationMonthlyMetrics(**m) for m in history],
    )


async def _handle_visibility_upload(file, db, current_user, visibility: str):
    config = ENTITY_CONFIG["courses"]

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se aceptan archivos CSV")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "El archivo no es un texto UTF-8 válido")

    try:
        identifiers = _validate_and_parse_csv(text, config["column"], config["label_plural"])
    except ValueError as e:
        raise HTTPException(400, str(e))

    batch_id = str(uuid.uuid4())
    create_batch(db, batch_id, "courses", "visibility", len(identifiers), current_user.modalidad)

    for identifier in identifiers:
        add_item(db, batch_id, identifier, detail={"visibility": visibility})
    db.commit()

    process_operation_batch.delay(batch_id)

    verb_label = "mostrar" if visibility == "show" else "ocultar"
    logger.info(f"Lote {batch_id} (cambiar visibilidad a {visibility} de {len(identifiers)} cursos) "
                f"encolado por {current_user.username}")

    return CsvUploadResponse(
        batch_id=batch_id, entity_type="courses", action="visibility",
        total=len(identifiers),
        message=f"Se encolaron {len(identifiers)} cursos para {verb_label}.",
    )


async def _handle_upload(file, db, current_user, entity_type, action, default_role=None):
    config = ENTITY_CONFIG[entity_type]

    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Solo se aceptan archivos CSV")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "El archivo no es un texto UTF-8 válido")

    try:
        is_create_users = entity_type == "users" and action == "create"
        is_create_categories = entity_type == "categories" and action == "create"
        if is_create_users:
            users = _validate_users_csv(text, default_role=default_role)
            identifiers = [u["username"] for u in users]
        elif is_create_categories:
            categories = _validate_categories_csv(text)
            identifiers = [c["name"] for c in categories]
        else:
            identifiers = _validate_and_parse_csv(text, config["column"], config["label_plural"])
    except ValueError as e:
        raise HTTPException(400, str(e))

    batch_id = str(uuid.uuid4())
    create_batch(db, batch_id, entity_type, action, len(identifiers), current_user.modalidad)

    if is_create_users:
        for user in users:
            add_item(db, batch_id, user["username"], detail={
                "firstname": user["firstname"], "lastname": user["lastname"],
                "email": user["email"], "password": user.get("password"),
                "role1": user.get("role1"),
                "forcepasswordchange": user.get("forcepasswordchange"),
            })
    elif is_create_categories:
        for cat in categories:
            add_item(db, batch_id, cat["name"], detail={
                "idnumber": cat.get("idnumber"), "parent": cat.get("parent"),
                "description": cat.get("description"), "visible": cat.get("visible"),
            })
    else:
        for identifier in identifiers:
            add_item(db, batch_id, identifier)
    db.commit()

    process_operation_batch.delay(batch_id)

    verb = "eliminación" if action == "delete" else "creación"
    logger.info(f"Lote {batch_id} ({verb} de {len(identifiers)} {config['label_plural']}) "
                f"encolado por {current_user.username}")

    return CsvUploadResponse(
        batch_id=batch_id, entity_type=entity_type, action=action,
        total=len(identifiers),
        message=f"Se encolaron {len(identifiers)} {config['label_plural']} para {verb}.",
    )
