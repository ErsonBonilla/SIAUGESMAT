"""
Métricas ligeras en memoria para monitoreo interno del backend.

Almacena contadores y sumas en diccionarios thread-safe.
NO requiere dependencias externas (Prometheus, StatsD, etc.).
"""

import time
from collections import Counter, defaultdict
from threading import Lock
from typing import Dict

_moodle: Dict[str, Counter] = defaultdict(Counter)
_lock = Lock()


def _key(name: str, **labels) -> str:
    parts = [name]
    for k, v in sorted(labels.items()):
        if v is not None:
            parts.append(f"{k}={v}")
    return ":".join(parts)


def inc(name: str, **labels):
    """Incrementa un contador."""
    k = _key(name, **labels)
    with _lock:
        _moodle[name][k] += 1


def observe(name: str, value: float, **labels):
    """Acumula un valor para calcular promedios (sum + count)."""
    k = _key(name, **labels)
    with _lock:
        _moodle[name][k + ":count"] += 1
        _moodle[name][k + ":sum"] += value


def get_snapshot() -> Dict[str, Dict[str, int]]:
    """Retorna una copia snapshot de todas las métricas."""
    with _lock:
        return {k: dict(v) for k, v in _moodle.items()}


def reset():
    """Reinicia todas las métricas (útil en tests)."""
    with _lock:
        _moodle.clear()
