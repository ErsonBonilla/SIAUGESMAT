#!/usr/bin/env python3
"""
Orquestador del e2e en modo simulado.

Levanta el Moodle simulado (HTTP mock), el worker Celery aislado y la API
apuntando a él, ejecuta `ejecutar_test.py` contra la API y limpia al final.

Uso:
    python e2e/ejecutar_simulado.py
    python e2e/ejecutar_simulado.py e2e/fixtures/ibague.xlsx --mode users
    python e2e/ejecutar_simulado.py e2e/fixtures/ibague.xlsx --mode both --confirm --mantener
    python e2e/ejecutar_simulado.py --reset-db --quiet

Requiere (como en el README "Modo simulado"):
    - BD PostgreSQL `siaugesmat_e2e` migrada (alembic upgrade head)
    - Redis local (redis://localhost:6379/5 se usa por defecto)
    - El fixture Excel indicado (o el default e2e/fixtures/ibague.xlsx)

La salida del runner y los logs de mock/worker/API quedan en
`e2e/tmp_reports/` (salvo con `--quiet`).
"""

import argparse
import contextlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

from stack_e2e import (
    RAIZ,
    comando_api,
    comando_moodle,
    comando_worker,
    construir_env,
    python_ejecutable,
)

sys.path.insert(0, str(RAIZ))

DIR_LOGS = RAIZ / "e2e" / "tmp_reports"
DIR_UPLOADS = RAIZ / "e2e" / "tmp_uploads"


def _liberar_puerto(port: int) -> None:
    """Mata cualquier proceso que esté escuchando en `port` (residual de corridas previas)."""
    try:
        salida = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return
    pids = set()
    for linea in salida.splitlines():
        if f":{port} " in linea and "LISTENING" in linea:
            partes = linea.split()
            if partes:
                pids.add(partes[-1])
    for pid in pids:
        with contextlib.suppress(Exception):
            subprocess.run(["taskkill", "/F", "/T", "/PID", pid], capture_output=True, timeout=10)


def _esperar_salud(url: str, timeout: int = 60) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    raise RuntimeError(f"La API no respondio en {timeout}s: {url}")


def _esperar_puerto(port: int, timeout: int = 30) -> None:
    """Espera a que algo escuche en `port` (health del mock)."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        with socket.socket() as s:
            s.settimeout(1)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                pass
        time.sleep(1)
    raise RuntimeError(f"El servicio en el puerto {port} no respondio en {timeout}s")


def _resetear_db(database_url: str) -> None:
    """Trunca las tablas de la BD e2e para dejar un estado limpio.

    Los nombres de tabla se derivan del metadata de SQLAlchemy (sin drift
    cuando se agregan tablas).
    """
    import psycopg2

    import app.db.modelos  # noqa: F401  (registra las tablas en el metadata)
    from app.db.base import Base

    tablas = [t.name for t in Base.metadata.sorted_tables]
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"TRUNCATE TABLE {', '.join(tablas)} RESTART IDENTITY CASCADE")
    conn.close()
    print(">> BD e2e reseteada", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="e2e simulado (Moodle mock + worker + API)")
    parser.add_argument("file", nargs="?", default="e2e/fixtures/ibague.xlsx")
    parser.add_argument("--mode", default="users", choices=["users", "courses", "both"])
    parser.add_argument("--semester", default="2026B")
    parser.add_argument("--modalidad", default="DISTANCIA")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--moodle-port", type=int, default=8800)
    parser.add_argument("--api-port", type=int, default=8001)
    parser.add_argument(
        "--database-url",
        default="postgresql://postgres:admin@localhost:5432/siaugesmat_e2e",
    )
    parser.add_argument("--redis-url", default="redis://localhost:6379/5")
    parser.add_argument("--mantener", action="store_true", help="no terminar los procesos al final")
    parser.add_argument(
        "--reset-db", action="store_true", help="truncar las tablas de la BD e2e antes de correr"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="no volcar logs de mock/worker/API (a DEVNULL)"
    )
    args = parser.parse_args()

    if args.reset_db:
        _resetear_db(args.database_url)

    python = python_ejecutable()
    env = construir_env(
        modalidad=args.modalidad,
        moodle_port=args.moodle_port,
        database_url=args.database_url,
        redis_url=args.redis_url,
        upload_dir=DIR_UPLOADS,
        report_dir=DIR_LOGS,
        forzar=True,
    )
    DIR_UPLOADS.mkdir(parents=True, exist_ok=True)
    DIR_LOGS.mkdir(parents=True, exist_ok=True)

    api_url = f"http://127.0.0.1:{args.api_port}"

    procesos: list[subprocess.Popen] = []
    archivos_log: list = []

    def _destino_log(nombre: str):
        if args.quiet:
            return subprocess.DEVNULL
        fh = (DIR_LOGS / f"{nombre}.log").open("ab")
        archivos_log.append(fh)
        return fh

    _liberar_puerto(args.moodle_port)
    _liberar_puerto(args.api_port)

    print(">> Moodle simulado (mock HTTP)", flush=True)
    procesos.append(
        subprocess.Popen(
            comando_moodle(python, args.moodle_port),
            cwd=RAIZ,
            env=env,
            stdout=_destino_log("moodle"),
            stderr=subprocess.STDOUT,
        )
    )
    _esperar_puerto(args.moodle_port)

    print(f">> Worker Celery aislado ({args.redis_url})", flush=True)
    procesos.append(
        subprocess.Popen(
            comando_worker(python),
            cwd=RAIZ,
            env=env,
            stdout=_destino_log("worker"),
            stderr=subprocess.STDOUT,
        )
    )

    print(f">> API aislada ({api_url})", flush=True)
    procesos.append(
        subprocess.Popen(
            comando_api(python, args.api_port),
            cwd=RAIZ,
            env=env,
            stdout=_destino_log("api"),
            stderr=subprocess.STDOUT,
        )
    )

    try:
        _esperar_salud(f"{api_url}/health")
        print(">> API lista", flush=True)

        cmd = [
            python,
            "e2e/ejecutar_test.py",
            args.file,
            "--mode",
            args.mode,
            "--semester",
            args.semester,
            "--modalidad",
            args.modalidad,
            "--url",
            api_url,
        ]
        if args.confirm:
            cmd.append("--confirm")
        marca = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        log_runner = DIR_LOGS / f"runner_{marca}.log"
        with log_runner.open("wb") as fout:
            print(f">> Ejecutando e2e (log: {log_runner})", flush=True)
            rc = subprocess.call(cmd, cwd=RAIZ, env=env, stdout=fout, stderr=subprocess.STDOUT)
        print(f">> e2e terminó con rc={rc}", flush=True)
        return rc
    finally:
        if not args.mantener:
            print(">> Deteniendo procesos...", flush=True)
            for p in procesos:
                if p.poll() is None:
                    with contextlib.suppress(Exception):
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                            capture_output=True,
                            timeout=10,
                        )
            _liberar_puerto(args.moodle_port)
            _liberar_puerto(args.api_port)
        for fh in archivos_log:
            with contextlib.suppress(Exception):
                fh.close()


if __name__ == "__main__":
    sys.exit(main())
