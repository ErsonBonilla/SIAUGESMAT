import csv
import io
import logging
import os
import tempfile
import zipfile
from typing import Dict, List, Tuple

from app.core.entity_config import ENTITY_CONFIG
from app.db.models import OperationBatch, OperationItem

logger = logging.getLogger(__name__)


def build_batch_report_zip(batch: OperationBatch, items: List[OperationItem]) -> Tuple[str, str]:
    """Genera un ZIP con CSVs de resultados para un lote de operaciones.

    Returns:
        (zip_path, zip_filename) — la ruta al archivo temporal y el nombre sugerido.
    """
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
        {"campo": "Batch ID", "valor": batch.batch_id},
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

    zip_filename = f"reportes_{batch.action}_{batch.entity_type}_{batch.batch_id[:8]}.zip"
    return zip_path, zip_filename
