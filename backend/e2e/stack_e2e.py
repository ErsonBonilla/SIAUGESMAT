#!/usr/bin/env python3
"""
Configuración compartida del stack e2e aislado (Moodle simulado + worker + API).

Centraliza el armado del entorno (env) y los comandos de los tres servicios para
que `levantar_stack_e2e.py` (modo desacoplado) y `ejecutar_simulado.py`
(orquestador en primer plano) no dupliquen lógica ni diverjan en valores
(p. ej. `localhost` vs `127.0.0.1`).

Regla de aislamiento: las variables MOODLE_*__<modalidad> SIEMPRE se sobreescriben
apuntando al mock, para que ningún run de e2e toque la instancia real de Moodle.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

DATABASE_URL_DEFAULT = "postgresql://postgres:admin@localhost:5432/siaugesmat_e2e"
REDIS_URL_DEFAULT = "redis://localhost:6380/5"

UPLOAD_DIR_DEFAULT = RAIZ / "e2e" / "tmp_uploads"
REPORT_DIR_DEFAULT = RAIZ / "e2e" / "tmp_reports"

MODALIDAD_DEFAULT = "DISTANCIA"
MOODLE_TOKEN = "tokendemo"
MOODLE_VERSION = "3.9"


def construir_env(
    *,
    modalidad: str = MODALIDAD_DEFAULT,
    moodle_port: int = 8800,
    database_url: str = DATABASE_URL_DEFAULT,
    redis_url: str = REDIS_URL_DEFAULT,
    upload_dir: str | Path = UPLOAD_DIR_DEFAULT,
    report_dir: str | Path = REPORT_DIR_DEFAULT,
    forzar: bool = False,
) -> dict[str, str]:
    """Construye el entorno de los subprocesos del stack e2e.

    - ``forzar=True``: los valores de BD/Redis/upload/report sobreescriben lo
      que venga del entorno padre (necesario para aislar el run).
    - ``forzar=False``: se respeta una variable ya exportada (setdefault),
      salvo las ``MOODLE_*__<modalidad>`` que siempre apuntan al mock.
    """
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    for clave, valor in (("DATABASE_URL", database_url), ("REDIS_URL", redis_url)):
        if forzar:
            env[clave] = valor
        else:
            env.setdefault(clave, valor)
    env[f"MOODLE_URL__{modalidad}"] = f"http://127.0.0.1:{moodle_port}"
    env[f"MOODLE_TOKEN__{modalidad}"] = MOODLE_TOKEN
    env[f"MOODLE_VERSION__{modalidad}"] = MOODLE_VERSION
    for clave, valor in (("UPLOAD_DIR", upload_dir), ("REPORT_DIR", report_dir)):
        env[clave] = str(valor)
    return env


def comando_moodle(python: str, port: int) -> list[str]:
    return [python, "e2e/moodle_simulado.py", "--port", str(port)]


def comando_worker(python: str) -> list[str]:
    return [
        python,
        "-m",
        "celery",
        "-A",
        "app.celery_app.celery_app",
        "worker",
        "--loglevel=info",
        "--pool=solo",
    ]


def comando_api(python: str, port: int) -> list[str]:
    return [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)]


def python_ejecutable() -> str:
    return sys.executable
