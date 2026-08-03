"""Plan de logs del análisis (FASE 2) — transformaciones puras.

Convierte el resultado de la comparación en entradas de log listas para
persistir, sin tocar la base de datos.
"""

ALERT_ACTION_BY_REASON = {
    "disappeared_recent": "alert_disappeared_recent",
    "teacher_change_recent": "alert_teacher_change_recent",
    "disappeared": "alert_disappeared",
    "orphan_course": "alert_orphan_course",
}

Entry = tuple[str, str, dict[str, object] | None]


def plan_log_entries(
    comparison: dict,
    fullname_map: dict[str, str] | None = None,
) -> list[Entry]:
    """Deriva las entradas de log (action, identifier, detail) del plan.

    Los logs de comparación se emiten con prefijo ``planned_`` para
    distinguirlos de las acciones realmente ejecutadas. Las alertas usan su
    propia acción y enriquecen el detail con ``fullname`` y ``professor``.

    Las alertas con motivo desconocido se descartan.
    """
    fullname_lookup = fullname_map or {}
    entries: list[Entry] = []

    for entry in comparison.get("logs", []):
        entries.append((
            f"planned_{entry.get('action', 'unknown')}",
            entry.get("identifier", ""),
            entry.get("detail"),
        ))

    for alert in comparison.get("alerts", []):
        action = ALERT_ACTION_BY_REASON.get(alert.get("reason"))
        if not action:
            continue
        detail = {
            key: alert[key]
            for key in ("reason", "age_seconds", "old_professor", "new_professor")
            if alert.get(key) is not None
        }
        sn = alert.get("shortname", "")
        detail["fullname"] = fullname_lookup.get(sn, "")
        detail.setdefault(
            "professor",
            alert.get("new_professor") or alert.get("old_professor") or "",
        )
        entries.append((action, sn, detail))

    return entries
