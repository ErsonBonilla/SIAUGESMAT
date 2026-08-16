import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.modelos import Ejecucion, ItemOperacion, LoteOperacion
from app.repositories.repositorio_ejecuciones import ESTADOS_EJECUCION_ACTIVA

logger = logging.getLogger(__name__)


def obtener_lote(db: Session, id_lote: str) -> LoteOperacion | None:
    return db.query(LoteOperacion).filter_by(id_lote=id_lote).first()


def obtener_lote_activo(db: Session, modalidad: str) -> LoteOperacion | None:
    """Devuelve un lote de operaciones en curso (con items pendientes o en
    proceso) para una modalidad."""
    return (
        db.query(LoteOperacion)
        .join(ItemOperacion, ItemOperacion.id_lote == LoteOperacion.id_lote)
        .filter(
            LoteOperacion.modalidad == modalidad,
            ItemOperacion.estado.in_(["pending", "processing"]),
        )
        .first()
    )


def obtener_items_pendientes(db: Session, id_lote: str) -> list[ItemOperacion]:
    return db.query(ItemOperacion).filter_by(id_lote=id_lote, estado="pending").all()


def resolver_items_huerfanos(db: Session) -> list[ItemOperacion]:
    """Marca como 'failed' los items pending/processing huérfanos.

    Un item queda huérfano cuando su ejecución ya finalizó (completed, failed,
    cancelled) pero el item sigue en pending/processing. El reset de arranque
    del worker lo devuelve a 'pending' y, como el chord y el sweeper solo
    operan sobre ejecuciones activas, nadie lo reclama: su lote queda
    "activo" para siempre y bloquea subidas (get_active_batch). En lugar de
    resucitarlo, esta limpieza lo resuelve como failed.

    Returns:
        Lista de items resueltos (marcados como failed).
    """
    items = (
        db.query(ItemOperacion).filter(ItemOperacion.estado.in_(["pending", "processing"])).all()
    )
    by_execution: dict[int, list[ItemOperacion]] = {}
    for item in items:
        eid = (item.detalle or {}).get("execution_id")
        if eid:
            by_execution.setdefault(int(eid), []).append(item)

    if not by_execution:
        return []

    ejecuciones = db.query(Ejecucion).filter(Ejecucion.id.in_(by_execution)).all()
    active_ids = {ex.id for ex in ejecuciones if ex.estado in ESTADOS_EJECUCION_ACTIVA}

    orphaned: list[ItemOperacion] = []
    for eid, exec_items in by_execution.items():
        if eid in active_ids:
            continue
        for item in exec_items:
            item.estado = "failed"
            item.mensaje_error = "Ejecución finalizada, item huérfano"
            item.actualizado_en = datetime.now(UTC)
            orphaned.append(item)

    if orphaned:
        db.commit()
        logger.warning(f"Resueltos {len(orphaned)} items huérfanos de ejecuciones finalizadas")

    return orphaned


def crear_lote(
    db: Session, id_lote: str, tipo_entidad: str, accion: str, total: int, modalidad: str
) -> LoteOperacion:
    lote = LoteOperacion(
        id_lote=id_lote,
        tipo_entidad=tipo_entidad,
        accion=accion,
        total=total,
        modalidad=modalidad,
    )
    db.add(lote)
    db.flush()
    db.commit()
    return lote


def agregar_item(
    db: Session, id_lote: str, identificador: str, detalle: dict = None, estado: str = "pending"
) -> ItemOperacion:
    item = ItemOperacion(
        id_lote=id_lote,
        identificador=identificador,
        detalle=detalle,
        estado=estado,
    )
    db.add(item)
    return item


def obtener_item(db: Session, item_id: int) -> ItemOperacion | None:
    return db.query(ItemOperacion).filter(ItemOperacion.id == item_id).first()


def reclamar_item(db: Session, item_id: int) -> bool:
    """Reclama atómicamente un item moviéndolo de pending a processing.

    Usa ``UPDATE ... WHERE estado='pending'`` para evitar que dos workers
    procesen el mismo item tras un relaunch del sweeper.
    """
    result = (
        db.query(ItemOperacion)
        .filter(ItemOperacion.id == item_id, ItemOperacion.estado == "pending")
        .update(
            {
                ItemOperacion.estado: "processing",
                ItemOperacion.actualizado_en: datetime.now(UTC),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return result > 0


def actualizar_item(
    db: Session, item_id: int, estado: str, mensaje_error: str = None
) -> ItemOperacion | None:
    item = db.query(ItemOperacion).filter(ItemOperacion.id == item_id).first()
    if item:
        item.estado = estado
        if mensaje_error:
            item.mensaje_error = mensaje_error
        item.intento = (item.intento or 0) + 1
        item.actualizado_en = datetime.now(UTC)
        db.commit()
    return item


def actualizar_conteos_lote(
    db: Session, id_lote: str, completados: int = 0, fallidos: int = 0
) -> None:
    lote = db.query(LoteOperacion).filter_by(id_lote=id_lote).first()
    if lote:
        if completados:
            lote.completados = (lote.completados or 0) + completados
        if fallidos:
            lote.fallidos = (lote.fallidos or 0) + fallidos
        db.commit()


def completar_lote(db: Session, id_lote: str) -> None:
    lote = db.query(LoteOperacion).filter_by(id_lote=id_lote).first()
    if lote:
        lote.completado_en = datetime.now(UTC)
        db.commit()


def obtener_estado_lote(db: Session, id_lote: str) -> dict:
    base_q = db.query(ItemOperacion).filter_by(id_lote=id_lote)
    return {
        "total": base_q.count(),
        "pending": base_q.filter_by(estado="pending").count(),
        "processing": base_q.filter_by(estado="processing").count(),
        "paused": base_q.filter_by(estado="paused").count(),
        "completed": base_q.filter_by(estado="completed").count(),
        "failed": base_q.filter_by(estado="failed").count(),
        "cancelled": base_q.filter_by(estado="cancelled").count(),
    }


def obtener_items_lote(db: Session, id_lote: str, offset: int, limit: int) -> list[ItemOperacion]:
    return (
        db.query(ItemOperacion)
        .filter_by(id_lote=id_lote)
        .order_by(ItemOperacion.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


def obtener_todos_items_lote(db: Session, id_lote: str) -> list[ItemOperacion]:
    return db.query(ItemOperacion).filter_by(id_lote=id_lote).order_by(ItemOperacion.id).all()


def pausar_lote(db: Session, id_lote: str) -> int:
    pausados = (
        db.query(ItemOperacion)
        .filter_by(id_lote=id_lote, estado="pending")
        .update(
            {"estado": "paused", "actualizado_en": datetime.now(UTC)}, synchronize_session=False
        )
    )
    db.commit()
    return pausados


def reanudar_lote(db: Session, id_lote: str) -> int:
    reanudados = (
        db.query(ItemOperacion)
        .filter_by(id_lote=id_lote, estado="paused")
        .update(
            {"estado": "pending", "actualizado_en": datetime.now(UTC)}, synchronize_session=False
        )
    )
    db.commit()
    return reanudados


def cancelar_lote(db: Session, id_lote: str) -> int:
    cancelados = (
        db.query(ItemOperacion)
        .filter(
            ItemOperacion.id_lote == id_lote,
            ItemOperacion.estado.in_(["pending", "processing", "paused"]),
        )
        .update(
            {"estado": "cancelled", "actualizado_en": datetime.now(UTC)}, synchronize_session=False
        )
    )
    db.commit()
    return cancelados


def eliminar_lote(db: Session, id_lote: str) -> bool:
    lote = obtener_lote(db, id_lote)
    if not lote:
        return False
    db.query(ItemOperacion).filter_by(id_lote=id_lote).delete(synchronize_session=False)
    db.delete(lote)
    db.commit()
    return True


def obtener_conteos_pausados_lote(db: Session, id_lotes: list[str]) -> dict[str, int]:
    if not id_lotes:
        return {}
    rows = (
        db.query(ItemOperacion.id_lote, func.count(ItemOperacion.id))
        .filter(ItemOperacion.id_lote.in_(id_lotes), ItemOperacion.estado == "paused")
        .group_by(ItemOperacion.id_lote)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def eliminar_lotes_antiguos(db: Session, days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    old_batches = db.query(LoteOperacion).filter(LoteOperacion.creado_en < cutoff).all()
    id_lotes = [lote.id_lote for lote in old_batches]
    if id_lotes:
        db.query(ItemOperacion).filter(ItemOperacion.id_lote.in_(id_lotes)).delete(
            synchronize_session=False
        )
    deleted = 0
    for lote in old_batches:
        db.delete(lote)
        deleted += 1
    db.commit()
    return deleted


def listar_lotes(
    db: Session,
    tipo_entidad: str = None,
    accion: str = None,
    modalidad: str = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[LoteOperacion]]:
    query = db.query(LoteOperacion)
    if tipo_entidad:
        query = query.filter(LoteOperacion.tipo_entidad == tipo_entidad)
    if accion:
        query = query.filter(LoteOperacion.accion == accion)
    if modalidad:
        query = query.filter(LoteOperacion.modalidad == modalidad)
    total = query.count()
    lotes = query.order_by(LoteOperacion.creado_en.desc()).offset(offset).limit(limit).all()
    return total, lotes


def obtener_analitica_operaciones(
    db: Session,
    modalidad: str = None,
    months: int = 12,
    tipo_entidad: str = None,
    accion: str = None,
) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(days=months * 30)
    base_filters = [LoteOperacion.creado_en >= cutoff]
    if modalidad:
        base_filters.append(LoteOperacion.modalidad == modalidad)

    monthly_batches = db.query(LoteOperacion).filter(*base_filters)
    if tipo_entidad:
        monthly_batches = monthly_batches.filter(LoteOperacion.tipo_entidad == tipo_entidad)
    if accion:
        monthly_batches = monthly_batches.filter(LoteOperacion.accion == accion)

    raw_monthly = monthly_batches.all()

    base_metrics = {
        "users_created": 0,
        "users_deleted": 0,
        "categories_created": 0,
        "categories_deleted": 0,
        "courses_deleted": 0,
        "total_errors": 0,
    }

    months_data: dict[str, dict] = {}

    for b in raw_monthly:
        month = b.creado_en.strftime("%Y-%m")
        if month not in months_data:
            months_data[month] = dict(base_metrics, month=month)

        m = months_data[month]
        m["total_errors"] += b.fallidos or 0
        key = f"{b.tipo_entidad}_{b.accion}"
        if key == "users_create":
            m["users_created"] += b.completados or 0
        elif key == "users_delete":
            m["users_deleted"] += b.completados or 0
        elif key == "categories_create":
            m["categories_created"] += b.completados or 0
        elif key == "categories_delete":
            m["categories_deleted"] += b.completados or 0
        elif key == "courses_delete":
            m["courses_deleted"] += b.completados or 0

    return sorted(months_data.values(), key=lambda m: m["month"])
