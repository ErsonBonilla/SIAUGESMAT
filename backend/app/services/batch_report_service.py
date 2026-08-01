import csv
import io
import logging
import os
import tempfile
import zipfile
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.entity_config import ENTITY_CONFIG
from app.db.models import OperationBatch, OperationItem
from app.services.report_utils import write_csv, create_zip, list_csv_files, get_csv_path

logger = logging.getLogger(__name__)

REPORT_BASE = os.path.join(settings.REPORT_DIR, "batch")


def _batch_dir(batch_id: str) -> str:
    return os.path.join(REPORT_BASE, batch_id)


def _build_rows(batch: OperationBatch, items: List[OperationItem]) -> Dict[str, list]:
    """Returns {csv_name: (headers, rows)} for each CSV to generate."""
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

    csvs: Dict[str, tuple] = {}

    if all_rows:
        csvs["resultados"] = (base_headers, all_rows)
    if failed_rows:
        csvs["fallidos"] = (base_headers, failed_rows)
    if batch.action == "create" and success_rows:
        csvs["creados"] = (base_headers, success_rows)
    if batch.action == "delete" and not_found_rows:
        csvs["no_encontrados"] = (["identificador", "estado", "error", "intentos"], not_found_rows)

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
    csvs["resumen"] = (["campo", "valor"], resumen_rows)

    return csvs


def save_batch_reports(batch: OperationBatch, items: List[OperationItem]) -> str:
    """Genera y persiste CSVs individuales en disco.

    Returns:
        Ruta al directorio con los reportes.
    """
    csvs = _build_rows(batch, items)
    batch_dir = _batch_dir(batch.batch_id)
    os.makedirs(batch_dir, exist_ok=True)

    for name, (headers, rows) in csvs.items():
        filepath = os.path.join(batch_dir, f"{name}.csv")
        write_csv(filepath, headers, rows)
        logger.info(f"Reporte batch {name}.csv: {len(rows)} filas")

    create_zip(batch_dir, batch_dir + ".zip")

    logger.info(f"Reportes batch guardados en: {batch_dir}")
    return batch_dir


def list_batch_reports(batch_id: str) -> List[Dict[str, str]]:
    return list_csv_files(_batch_dir(batch_id))


def get_batch_report_path(batch_id: str, report_name: str) -> Optional[str]:
    return get_csv_path(_batch_dir(batch_id), report_name)


def build_batch_report_zip(batch: OperationBatch, items: List[OperationItem]) -> Tuple[str, str]:
    """Genera ZIP temporal para descarga (compatibilidad con endpoint legacy)."""
    csvs = _build_rows(batch, items)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        zip_path = tmp.name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, (headers, rows) in csvs.items():
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(headers)
            for row in rows:
                if isinstance(row, dict):
                    writer.writerow([row.get(h, "") for h in headers])
                else:
                    writer.writerow(row)
            buf.seek(0)
            zf.writestr(f"{name}.csv", buf.getvalue().encode("utf-8-sig"))

    zip_filename = f"reportes_{batch.action}_{batch.entity_type}_{batch.batch_id[:8]}.zip"
    return zip_path, zip_filename
