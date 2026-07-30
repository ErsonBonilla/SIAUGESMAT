import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import OperationItem

logger = logging.getLogger(__name__)

STUCK_ITEM_TIMEOUT_MINUTES = 30


def reset_stuck_items(
    db: Session,
    batch_id_prefix: Optional[str] = None,
    execution_id: Optional[str] = None,
    increment_attempt: bool = False,
    cutoff_minutes: int = STUCK_ITEM_TIMEOUT_MINUTES,
) -> List[OperationItem]:
    """Resetea items stuck en 'processing' más allá del timeout.

    Args:
        db: Sesión de base de datos.
        batch_id_prefix: Filtro LIKE para batch_id (ej. ``"etl_3_%"``).
        execution_id: Si se provee, se concatena al prefijo.
        increment_attempt: Si True, incrementa el contador de intentos.
        cutoff_minutes: Minutos de tolerancia antes de considerar stuck.

    Returns:
        Lista de items reseteados.
    """
    query = db.query(OperationItem).filter(
        OperationItem.status == "processing",
        OperationItem.updated_at < datetime.now(timezone.utc) - timedelta(minutes=cutoff_minutes),
    )
    if batch_id_prefix:
        like_pattern = batch_id_prefix
        if execution_id:
            like_pattern = f"{like_pattern}%_{execution_id}"
        query = query.filter(OperationItem.batch_id.like(like_pattern))

    stuck: List[OperationItem] = query.all()
    for item in stuck:
        item.status = "pending"
        item.error_message = "Reintentando tras timeout por crash"
        if increment_attempt:
            item.attempt = (item.attempt or 0) + 1

    if stuck:
        db.commit()
        logger.warning(f"Reseteados {len(stuck)} items stuck en 'processing'")

    return stuck
