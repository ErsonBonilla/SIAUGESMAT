import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.modelos import ItemOperacion

logger = logging.getLogger(__name__)

STUCK_ITEM_TIMEOUT_MINUTES = 30


def _ejecutar_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


def ejecutar_moodle_async(moodle, coro):
    """Ejecuta un coroutine y garantiza el cierre del servicio Moodle."""

    async def _ejecutar_y_cerrar():
        try:
            return await coro
        finally:
            await moodle.close()

    return _ejecutar_async(_ejecutar_y_cerrar())


def reiniciar_items_atascados(
    db: Session,
    batch_id_prefix: str | None = None,
    execution_id: str | None = None,
    increment_attempt: bool = False,
    cutoff_minutes: int = STUCK_ITEM_TIMEOUT_MINUTES,
) -> list[ItemOperacion]:
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
    query = db.query(ItemOperacion).filter(
        ItemOperacion.estado == "processing",
        ItemOperacion.actualizado_en < datetime.now(UTC) - timedelta(minutes=cutoff_minutes),
    )
    if batch_id_prefix:
        like_pattern = batch_id_prefix
        if execution_id:
            like_pattern = f"{like_pattern}%_{execution_id}"
        query = query.filter(ItemOperacion.id_lote.like(like_pattern))

    stuck: list[ItemOperacion] = query.all()
    for item in stuck:
        item.estado = "pending"
        item.mensaje_error = "Reintentando tras timeout por crash"
        if increment_attempt:
            item.intento = (item.intento or 0) + 1

    if stuck:
        db.commit()
        logger.warning(f"Reseteados {len(stuck)} items stuck en 'processing'")

    return stuck
