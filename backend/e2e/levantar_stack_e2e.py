#!/usr/bin/env python3
"""
Levanta el stack aislado de e2e (Moodle simulado + worker + API) como procesos
desacoplados, para que el tool `bash` de opencode retorne al instante.

En Windows, lanzar servicios long-lived con `Start-Process` desde el tool `bash`
hereda el pipe de stdout de opencode y la llamada queda `running` para siempre.
Este script usa `subprocess.Popen` con `DETACHED_PROCESS` (los servicios no
heredan el pipe) y redirige su salida a archivos, de modo que el comando termina
nada más lanzar los servicios.

Uso (desde `backend/`):
    python e2e/levantar_stack_e2e.py              # levanta mock :8800, worker, API :8001
    python e2e/levantar_stack_e2e.py --stop       # mata los árboles registrados
    python e2e/levantar_stack_e2e.py --api-port 8001 --moodle-port 8800
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from stack_e2e import (
    comando_api,
    comando_moodle,
    comando_worker,
    construir_env,
    python_ejecutable,
)

ESTADO_DIR = Path(tempfile.gettempdir()) / "siaugesmat_e2e"
ARCHIVO_PIDS = ESTADO_DIR / "stack.pids.json"

COMPONENTES = ("moodle", "worker", "api")


def _entorno(moodle_port: int) -> dict[str, str]:
    return construir_env(
        modalidad="DISTANCIA",
        moodle_port=moodle_port,
        upload_dir=ESTADO_DIR / "uploads",
        report_dir=ESTADO_DIR / "reports",
        forzar=False,
    )


def _lanzar(nombre: str, args: list[str], env: dict[str, str]) -> subprocess.Popen:
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    with (
        open(ESTADO_DIR / f"{nombre}.log", "ab") as out,
        open(ESTADO_DIR / f"{nombre}.err", "ab") as err,
    ):
        popen_kwargs: dict = {
            "cwd": Path(__file__).resolve().parents[1],
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": out,
            "stderr": err,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
            )
        else:
            popen_kwargs["start_new_session"] = True
        return subprocess.Popen(args, **popen_kwargs)


def levantar(moodle_port: int, api_port: int) -> dict[str, int]:
    env = _entorno(moodle_port)
    python = python_ejecutable()
    procs = {
        "moodle": _lanzar("moodle", comando_moodle(python, moodle_port), env),
        "worker": _lanzar("worker", comando_worker(python), env),
        "api": _lanzar("api", comando_api(python, api_port), env),
    }
    pids = {nombre: p.pid for nombre, p in procs.items()}
    ARCHIVO_PIDS.write_text(json.dumps(pids, indent=2), encoding="utf-8")
    return pids


def _matar(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(pid), 9)


def detener() -> None:
    if not ARCHIVO_PIDS.exists():
        print(f"No hay stack registrado ({ARCHIVO_PIDS})")
        return
    pids = json.loads(ARCHIVO_PIDS.read_text(encoding="utf-8"))
    for nombre, pid in pids.items():
        print(f"Deteniendo {nombre} (PID {pid})...")
        _matar(pid)
    ARCHIVO_PIDS.unlink(missing_ok=True)
    print("Stack e2e detenido.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Levanta o detiene el stack e2e aislado (mock Moodle + worker + API)."
    )
    parser.add_argument("--stop", action="store_true", help="detiene los servicios registrados")
    parser.add_argument(
        "--api-port", type=int, default=8001, help="puerto de la API (default 8001)"
    )
    parser.add_argument(
        "--moodle-port", type=int, default=8800, help="puerto del mock (default 8800)"
    )
    args = parser.parse_args()

    if args.stop:
        detener()
        return

    pids = levantar(args.moodle_port, args.api_port)
    print(f"Stack e2e levantado (PIDs en {ARCHIVO_PIDS}):")
    for nombre in COMPONENTES:
        print(f"  {nombre}: PID {pids[nombre]}")
    print(f"Logs en: {ESTADO_DIR}")
    print("Para detener: python e2e/levantar_stack_e2e.py --stop")


if __name__ == "__main__":
    main()
