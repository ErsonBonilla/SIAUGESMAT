#!/usr/bin/env python3
"""
Runner unificado para pruebas reales contra Moodle 3.9.

Uso:
    python tests/real/run_test.py fixtures/bajocalima.xlsx
    python tests/real/run_test.py fixtures/ibague.xlsx --mode users
    python tests/real/run_test.py fixtures/uraba.xlsx --mode both --confirm

Flujo:
    1. Genera token JWT automáticamente
    2. Sube el Excel al backend
    3. Dispara el procesamiento ETL
    4. Espera a que termine (polling cada 2s)
    5. Si requiere confirmación de delete masivo, llama a POST /confirm
    6. Muestra métricas finales
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = os.environ.get("SIAUGESMAT_URL", "http://localhost:8000")
API = f"{BASE_URL}/api/v1"


def upload_excel(filepath: str, semester: str, mode: str, modalidad: str, token: str) -> int:
    """Sube un archivo Excel y retorna el execution_id."""
    boundary = "----FormBoundarySIAUGESMAT"
    body = b""

    with open(filepath, "rb") as f:
        fd = f.read()

    filename = os.path.basename(filepath)
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
    body += b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
    body += fd

    for name, val in [("semester", semester), ("mode", mode), ("modalidad", modalidad)]:
        body += f"\r\n--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += val.encode()

    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(f"{API}/upload", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read().decode())
    return data["execution_id"]


def process_execution(eid: int, token: str) -> None:
    """Dispara el procesamiento de una ejecución."""
    req = urllib.request.Request(f"{API}/jobs/{eid}/process", method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    urllib.request.urlopen(req)


def confirm_execution(eid: int, token: str) -> None:
    """Confirma una ejecución bloqueada por delete masivo."""
    req = urllib.request.Request(f"{API}/jobs/{eid}/confirm", method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())


def get_status(eid: int, token: str) -> dict:
    """Obtiene el estado actual de una ejecución."""
    req = urllib.request.Request(f"{API}/jobs/{eid}")
    req.add_header("Authorization", f"Bearer {token}")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())


def poll_until_done(eid: int, token: str, auto_confirm: bool = False, interval: float = 2.0) -> dict:
    """Espera hasta que la ejecución termine o requiera confirmación."""
    last_phase = ""
    while True:
        try:
            status = get_status(eid, token)
        except urllib.error.HTTPError:
            time.sleep(interval)
            continue

        phase = status.get("current_phase", "")
        pct = status.get("progress_pct", 0)
        st = status.get("status", "unknown")

        if phase != last_phase:
            print(f"  [{st}] {pct or 0:.0f}% {phase}")
            last_phase = phase

        if st == "review_required":
            print(f"\n  [WARN] DELETE MASIVO detectado -- requiere confirmacion")
            if auto_confirm:
                print(f"  Confirmando automaticamente...")
                result = confirm_execution(eid, token)
                print(f"  Reanudado: {result['message']}")
                last_phase = ""
                continue
            else:
                print(f"  Usá --confirm para autorizar, o revisá en el frontend")
                return status

        if st in ("completed", "failed"):
            return status

        time.sleep(interval)


def print_results(status: dict) -> None:
    """Muestra un resumen de los resultados."""
    metrics = status.get("metrics", {}) or {}
    print(f"\n{'='*50}")
    print(f"Resultados — Ejecución #{status.get('id')}")
    print(f"  Status:     {status.get('status')}")
    print(f"  Progreso:   {status.get('progress_pct', 0):.0f}%")
    dur = status.get("duration_seconds", 0) or 0
    print(f"  Duración:   {dur:.1f}s")
    print(f"  Errores:    {status.get('errors_count', 0)}")

    keys = ["categories_created", "courses_created", "courses_deleted",
            "courses_activated", "courses_hidden", "users_created",
            "enrolments", "enrolment_errors", "alerts"]
    for k in keys:
        v = metrics.get(k, 0)
        if v:
            print(f"  {k}:  {v}")

    report = status.get("report_dir", "")
    if report:
        print(f"\n  Reportes: {report}")


def main():
    parser = argparse.ArgumentParser(description="Prueba real del pipeline ETL SIAUGESMAT")
    parser.add_argument("file", help="Archivo Excel a procesar")
    parser.add_argument("--mode", default="users", choices=["users", "courses", "both"],
                        help="Modo de procesamiento (default: users)")
    parser.add_argument("--semester", default="2026B", help="Semestre (default: 2026B)")
    parser.add_argument("--modalidad", default="DISTANCIA", help="Modalidad (default: DISTANCIA)")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirmar automáticamente el delete masivo si se requiere")
    parser.add_argument("--url", default=None,
                        help="URL del backend (default: http://localhost:8000)")
    args = parser.parse_args()

    if args.url:
        global API
        API = f"{args.url.rstrip('/')}/api/v1"

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"ERROR: Archivo no encontrado: {args.file}")
        sys.exit(1)

    # Generar token JWT
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    from app.core.security import create_access_token
    token = create_access_token({
        "sub": "1",
        "username": "admin",
        "modalidad": args.modalidad,
    })

    print(f"SIAUGESMAT - Prueba real")
    print(f"  Archivo:   {filepath.name}")
    print(f"  Mode:      {args.mode}")
    print(f"  Semestre:  {args.semester}")
    print(f"  Modalidad: {args.modalidad}")
    print()

    # Subir y procesar
    print("Subiendo archivo...")
    eid = upload_excel(str(filepath), args.semester, args.mode, args.modalidad, token)
    print(f"  Upload OK -- execution_id={eid}")

    print("Procesando...")
    process_execution(eid, token)

    status = poll_until_done(eid, token, auto_confirm=args.confirm)

    # Mostrar resultados
    if status.get("status") == "review_required":
        # Solo mostrar métricas parciales, no es error
        print_results({**status, "status": "review_required (pendiente confirmación)"})
    else:
        print_results(status)

    if status.get("status") == "completed":
        print("\n[OK] Pipeline completado exitosamente.")
    elif status.get("status") == "review_required":
        print("\n[PAUSED] Ejecucion pausada -- requiere confirmacion de delete masivo.")
    else:
        print(f"\n[FAIL] Pipeline fallo: {status.get('current_phase', '')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
