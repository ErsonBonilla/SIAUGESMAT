import csv
import logging
import os
import zipfile

logger = logging.getLogger(__name__)


def escribir_csv(filepath: str, headers: list[str], rows: list[dict | list]):
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            if isinstance(row, dict):
                writer.writerow([row.get(h, "") for h in headers])
            else:
                writer.writerow(row)


def crear_zip(directory: str, zip_path: str, extensions: tuple[str, ...] = (".csv",)):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(extensions):
                    file_path = os.path.join(root, file)
                    zf.write(file_path, os.path.relpath(file_path, directory))


def listar_archivos_csv(directory: str) -> list[dict[str, str]]:
    if not os.path.isdir(directory):
        return []
    reports = []
    for fname in sorted(os.listdir(directory)):
        if fname.endswith(".csv"):
            path = os.path.join(directory, fname)
            name = fname.replace(".csv", "")
            reports.append(
                {
                    "name": name,
                    "filename": fname,
                    "size": os.path.getsize(path),
                }
            )
    return reports


def obtener_ruta_csv(directory: str, report_name: str) -> str | None:
    base = os.path.basename(report_name)
    if base != report_name or base in (".", ".."):
        return None
    path = os.path.join(directory, f"{base}.csv")
    return path if os.path.exists(path) else None
