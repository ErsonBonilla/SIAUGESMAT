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
PATRONES_NO_ENCONTRADO = ("no encontrad", "not found", "notfound", "no existía")
VERBOS_ACCION_LOTE = {
    "create": "Creación",
    "delete": "Eliminación",
    "update": "Actualización",
    "rename": "Renombrado",
    "activate": "Activación",
    "hide": "Ocultamiento",
    "visibility": "Visibilidad",
}


def _directorio_lote(batch_id: str) -> str:
    seguro = os.path.basename(str(batch_id or "").strip())
    if not seguro or seguro in (".", ".."):
        raise ValueError(f"ID de lote inválido: {batch_id!r}")
    return os.path.join(REPORT_BASE, seguro)


def _valor_str(det: dict, clave: str, respaldo: str = "") -> str:
    val = det.get(clave)
    return str(val) if val is not None and val != "" else respaldo


def _construir_fila_item(batch: LoteOperacion, item: ItemOperacion) -> dict[str, str]:
    det = item.detalle or {}
    row = {
        "identificador": item.identificador,
        "estado": item.estado,
        "error": item.mensaje_error or "",
        "intentos": str(item.intento or 0),
    }
    if batch.tipo_entidad == "categories" and batch.accion == "create":
        row["idnumber"] = _valor_str(det, "idnumber")
        row["parent"] = _valor_str(det, "parent", "DISTANCIA")
        row["description"] = _valor_str(det, "description")
        row["visible"] = str(det.get("visible", 1))
    elif batch.tipo_entidad == "users" and batch.accion == "create":
        row["firstname"] = _valor_str(det, "firstname")
        row["lastname"] = _valor_str(det, "lastname")
        row["email"] = _valor_str(det, "email")
        row["rol"] = _valor_str(det, "role1")
    return row


def _es_error_no_encontrado(batch: LoteOperacion, item: ItemOperacion) -> bool:
    if batch.accion != "delete" or not item.mensaje_error:
        return False
    msg_lower = item.mensaje_error.lower()
    return any(w in msg_lower for w in PATRONES_NO_ENCONTRADO)


def _encabezados_lote(batch: LoteOperacion) -> list[str]:
    base = ["identificador", "estado", "error", "intentos"]
    if batch.tipo_entidad == "categories" and batch.accion == "create":
        return [*base, "idnumber", "parent", "description", "visible"]
    if batch.tipo_entidad == "users" and batch.accion == "create":
        return [*base, "firstname", "lastname", "email", "rol"]
    return base


def _filas_resumen_lote(batch: LoteOperacion, items: list[ItemOperacion]) -> list[dict[str, str]]:
    config = CONFIG_ENTIDADES.get(batch.tipo_entidad, CONFIG_ENTIDADES["courses"])
    action_verb = VERBOS_ACCION_LOTE.get(batch.accion, str(batch.accion or "Operación"))
    completed = sum(1 for i in items if i.estado == "completed")
    failed = sum(1 for i in items if i.estado == "failed")
    return [
        {"campo": "Tipo de entidad", "valor": config["label_plural"]},
        {"campo": "Operación", "valor": action_verb},
        {"campo": "Total", "valor": str(len(items))},
        {"campo": "Completados", "valor": str(completed)},
        {"campo": "Fallidos", "valor": str(failed)},
        {"campo": "ID de lote", "valor": batch.id_lote},
        {"campo": "Creado", "valor": batch.creado_en.isoformat() if batch.creado_en else ""},
        {
            "campo": "Completado",
            "valor": batch.completado_en.isoformat() if batch.completado_en else "",
        },
    ]


def _build_rows(batch: LoteOperacion, items: list[ItemOperacion]) -> dict[str, list]:
    """Returns {csv_name: (headers, rows)} for each CSV to generate."""
    all_rows, failed_rows, success_rows, not_found_rows = [], [], [], []
    for item in items:
        row = _construir_fila_item(batch, item)
        all_rows.append(row)
        if item.estado == "failed":
            failed_rows.append(row)
        elif item.estado == "completed":
            success_rows.append(row)
        if _es_error_no_encontrado(batch, item):
            not_found_rows.append(row)

    base_headers = _encabezados_lote(batch)
    csvs: dict[str, tuple] = {}

    if all_rows:
        csvs["resultados"] = (base_headers, all_rows)
    if failed_rows:
        csvs["fallidos"] = (base_headers, failed_rows)
    if batch.accion == "create" and success_rows:
        csvs["creados"] = (base_headers, success_rows)
    if not_found_rows:
        csvs["no_encontrados"] = (["identificador", "estado", "error", "intentos"], not_found_rows)

    csvs["resumen"] = (["campo", "valor"], _filas_resumen_lote(batch, items))
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
