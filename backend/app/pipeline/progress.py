"""Cálculo de progreso por fases (item_task) — transformaciones puras."""
from typing import Union

Number = Union[int, float]


def compute_phase_progress(
    phase3_total: Number,
    phase3_done: Number,
    phase4_total: Number,
    phase4_done: Number,
) -> float:
    """Porcentaje global de progreso según el avance de las fases 3 y 4.

    - Mientras la fase 3 esté en curso: 34 % → 62 %.
    - Con fase 3 terminada y fase 4 iniciada: 65 % → 85 %.
    - Sin items de ninguna fase: la fórmula combinada de respaldo.

    Redondea a 1 decimal. Los contadores se asumen >= 0.
    """
    if phase3_total > 0 and phase3_done < phase3_total:
        pct = 34.0 + (phase3_done / phase3_total) * 28.0
    elif phase4_total > 0:
        pct = 65.0 + (phase4_done / phase4_total) * 20.0
    else:
        total = phase3_total + phase4_total
        done = phase3_done + phase4_done
        pct = 34.0 + (done / max(total, 1)) * 28.0
    return round(pct, 1)
