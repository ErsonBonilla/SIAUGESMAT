import csv
import io
import logging
import os
import tempfile
import zipfile

from app.core.config import settings
from app.core.configuracion_entidades import CONFIG_ENTIDADES
from app.db.modelos import ItemOperacion, LoteOperacion
from app.services.utilidades_reportes import (
    crear_zip,
    escribir_csv,
    listar_archivos_csv,
    obtener_ruta_csv,
)

logger = logging.getLogger(__name__)

REPORT_BASE = os.path.join(settings.REPORT_DIR, "batch")


def _directorio_lote(batch_id: str) -> str:
    return os.path.join(REPORT_BASE, batch_id)


def _build_rows(batch: LoteOperacion, items: list[ItemOperacion]) -> dict[str, list]:
    """Returns {csv_name: (headers, rows)} for each CSV to generate."""
    config = CONFIG_ENTIDADES.get(batch.tipo_entidad, CONFIG_ENTIDADES["courses"])

    all_rows, failed_rows, success_rows, not_found_rows = [], [], [], []
    for item in items:
        det = item.detalle or {}
        row = {
            "identificador": item.identificador,
            "estado": item.estado,
            "error": item.mensaje_error or "",
            "intentos": str(item.intento or 0),
        }
        if batch.tipo_entidad == "categories" and batch.accion == "create":
            row["idnumber"] = det.get("idnumber") or ""
            row["parent"] = det.get("parent") or "DISTANCIA"
            row["description"] = det.get("description") or ""
            row["visible"] = str(det.get("visible", 1))
        if batch.tipo_entidad == "users" and batch.accion == "create":
            row["firstname"] = det.get("firstname") or ""
            row["lastname"] = det.get("lastname") or ""
            row["email"] = det.get("email") or ""
            row["rol"] = det.get("role1") or ""
        all_rows.append(row)

        if item.estado == "failed":
            failed_rows.append(row)
        if item.estado == "completed":
            success_rows.append(row)
        if batch.accion == "delete" and item.mensaje_error:
            msg_lower = item.mensaje_error.lower()
            if any(w in msg_lower for w in ("no encontrad", "not found", "notfound", "no existía")):
                not_found_rows.append(row)

    action_verb = "Eliminación" if batch.accion == "delete" else "Creación"
    base_headers = ["identificador", "estado", "error", "intentos"]
    if batch.tipo_entidad == "categories" and batch.accion == "create":
        base_headers += ["idnumber", "parent", "description", "visible"]
    elif batch.tipo_entidad == "users" and batch.accion == "create":
        base_headers += ["firstname", "lastname", "email", "rol"]

    csvs: dict[str, tuple] = {}

    if all_rows:
        csvs["resultados"] = (base_headers, all_rows)
    if failed_rows:
        csvs["fallidos"] = (base_headers, failed_rows)
    if batch.accion == "create" and success_rows:
        csvs["creados"] = (base_headers, success_rows)
    if batch.accion == "delete" and not_found_rows:
        csvs["no_encontrados"] = (["identificador", "estado", "error", "intentos"], not_found_rows)

    total = len(items)
    completed = sum(1 for i in items if i.estado == "completed")
    failed = sum(1 for i in items if i.estado == "failed")
    resumen_rows = [
        {"campo": "Tipo de entidad", "valor": config["label_plural"]},
        {"campo": "Operación", "valor": action_verb},
        {"campo": "Total", "valor": str(total)},
        {"campo": "Completados", "valor": str(completed)},
        {"campo": "Fallidos", "valor": str(failed)},
        {"campo": "Batch ID", "valor": batch.id_lote},
        {"campo": "Creado", "valor": batch.creado_en.isoformat() if batch.creado_en else ""},
        {
            "campo": "Completado",
            "valor": batch.completado_en.isoformat() if batch.completado_en else "",
        },
    ]
    csvs["resumen"] = (["campo", "valor"], resumen_rows)

    return csvs


def guardar_reportes_lote(batch: LoteOperacion, items: list[ItemOperacion]) -> str:
    """Genera y persiste CSVs individuales en disco.

    Returns:
        Ruta al directorio con los reportes.
    """
    csvs = _build_rows(batch, items)
    batch_dir = _directorio_lote(batch.id_lote)
    os.makedirs(batch_dir, exist_ok=True)

    for name, (headers, rows) in csvs.items():
        filepath = os.path.join(batch_dir, f"{name}.csv")
        escribir_csv(filepath, headers, rows)
        logger.info(f"Reporte batch {name}.csv: {len(rows)} filas")

    crear_zip(batch_dir, batch_dir + ".zip")

    logger.info(f"Reportes batch guardados en: {batch_dir}")
    return batch_dir


def listar_reportes_lote(batch_id: str) -> list[dict[str, str]]:
    return listar_archivos_csv(_directorio_lote(batch_id))


def obtener_ruta_reporte_lote(batch_id: str, report_name: str) -> str | None:
    return obtener_ruta_csv(_directorio_lote(batch_id), report_name)


def construir_zip_reportes_lote(
    batch: LoteOperacion, items: list[ItemOperacion]
) -> tuple[str, str]:
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

    zip_filename = f"reportes_{batch.accion}_{batch.tipo_entidad}_{batch.id_lote[:8]}.zip"
    return zip_path, zip_filename
