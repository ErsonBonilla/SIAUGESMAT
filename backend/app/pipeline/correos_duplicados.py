"""Núcleo puro para cuentas duplicadas por email.

Recibe filas de un CSV de Moodle (username, fecha_creacion, email) y agrupa
las cuentas que comparten correo, exponiendo cuál es la más antigua y la más
reciente por fecha de creación. No hace I/O: no consulta Moodle, no toca la
base de datos ni settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def parsear_fecha(text: str | None) -> datetime | None:
    """Convierte `fecha_creacion` (YYYY-MM-DD[ HH:MM:SS]). Devuelve None si no
    se puede interpretar."""
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None

    date_part, _, time_part = cleaned.partition(" ")
    parts = date_part.split("-")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(x) for x in parts)
    except ValueError:
        return None

    hour = minute = second = 0
    if time_part:
        sub = time_part.split(":")
        try:
            hour = int(sub[0]) if len(sub) > 0 else 0
            minute = int(sub[1]) if len(sub) > 1 else 0
            second = int(sub[2]) if len(sub) > 2 else 0
        except ValueError:
            return None

    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    except ValueError:
        return None


@dataclass(frozen=True)
class FilaUsuario:
    username: str
    email: str
    fecha_creacion: str
    date: datetime | None = None


@dataclass(frozen=True)
class GrupoDuplicados:
    email: str
    rows: tuple[FilaUsuario, ...]

    @property
    def count(self) -> int:
        return len(self.rows)

    def mas_antiguo(self) -> FilaUsuario | None:
        valid = [r for r in self.rows if r.date is not None]
        return min(valid, key=lambda r: r.date) if valid else None

    def mas_reciente(self) -> FilaUsuario | None:
        valid = [r for r in self.rows if r.date is not None]
        return max(valid, key=lambda r: r.date) if valid else None


def agrupar_filas(rows: list[dict]) -> list[GrupoDuplicados]:
    """Agrupa filas de CSV por email (normalizado a minúsculas).

    Cada fila debe tener las claves `username`, `email` y `fecha_creacion`.
    El resultado se ordena por email y por fecha/username para que sea
    reproducible.
    """
    grouped: dict[str, list[FilaUsuario]] = {}
    for row in rows:
        username = (row.get("username") or "").strip()
        email = (row.get("email") or "").strip().lower()
        if not username or not email:
            continue
        fecha = row.get("fecha_creacion") or ""
        grouped.setdefault(email, []).append(
            FilaUsuario(
                username=username,
                email=email,
                fecha_creacion=fecha,
                date=parsear_fecha(fecha),
            )
        )

    groups: list[GrupoDuplicados] = []
    for email in sorted(grouped):
        entries = sorted(grouped[email], key=lambda u: (u.date is None, u.date, u.username))
        groups.append(GrupoDuplicados(email=email, rows=tuple(entries)))
    return groups


def es_ambiguo(group: GrupoDuplicados) -> bool:
    """Un par es ambiguo si no hay dos cuentas o si no se puede decidir cuál es
    la más antigua (fecha no parseada o idéntica)."""
    if group.count != 2:
        return True
    older = group.mas_antiguo()
    if older is None:
        return True
    newer = group.mas_reciente()
    if newer is None:
        return True
    return older.date == newer.date
