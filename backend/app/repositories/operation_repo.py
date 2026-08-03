from datetime import UTC, datetime, timedelta

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.models import OperationBatch, OperationItem


def get_batch(db: Session, batch_id: str) -> OperationBatch | None:
    return db.query(OperationBatch).filter_by(batch_id=batch_id).first()


def get_pending_items(db: Session, batch_id: str) -> list[OperationItem]:
    return db.query(OperationItem).filter_by(
        batch_id=batch_id, status="pending"
    ).all()


def create_batch(db: Session, batch_id: str, entity_type: str, action: str,
                 total: int, modalidad: str) -> OperationBatch:
    batch = OperationBatch(
        batch_id=batch_id,
        entity_type=entity_type,
        action=action,
        total=total,
        modalidad=modalidad,
    )
    db.add(batch)
    db.flush()
    db.commit()
    return batch


def add_item(db: Session, batch_id: str, identifier: str, detail: dict = None,
             status: str = "pending") -> OperationItem:
    item = OperationItem(
        batch_id=batch_id,
        identifier=identifier,
        detail=detail,
        status=status,
    )
    db.add(item)
    return item


def get_item(db: Session, item_id: int) -> OperationItem | None:
    return db.query(OperationItem).filter(OperationItem.id == item_id).first()


def claim_item(db: Session, item_id: int) -> bool:
    """Reclama atómicamente un item moviéndolo de pending a processing.

    Usa ``UPDATE ... WHERE status='pending'`` para evitar que dos workers
    procesen el mismo item tras un relaunch del sweeper.
    """
    result = db.execute(
        text(
            "UPDATE operation_items SET status = 'processing', updated_at = now() "
            "WHERE id = :id AND status = 'pending'"
        ),
        {"id": item_id},
    )
    db.commit()
    return result.rowcount > 0


def update_item(db: Session, item_id: int, status: str, error_message: str = None) -> OperationItem | None:
    item = db.query(OperationItem).filter(OperationItem.id == item_id).first()
    if item:
        item.status = status
        if error_message:
            item.error_message = error_message
        item.attempt = (item.attempt or 0) + 1
        item.updated_at = datetime.now(UTC)
        db.commit()
    return item


def update_batch_counts(db: Session, batch_id: str, completed: int = 0, failed: int = 0) -> None:
    batch = db.query(OperationBatch).filter_by(batch_id=batch_id).first()
    if batch:
        if completed:
            batch.completed = (batch.completed or 0) + completed
        if failed:
            batch.failed = (batch.failed or 0) + failed
        db.commit()


def complete_batch(db: Session, batch_id: str) -> None:
    batch = db.query(OperationBatch).filter_by(batch_id=batch_id).first()
    if batch:
        batch.completed_at = datetime.now(UTC)
        db.commit()


def get_batch_status(db: Session, batch_id: str) -> dict:
    base_q = db.query(OperationItem).filter_by(batch_id=batch_id)
    return {
        "total": base_q.count(),
        "pending": base_q.filter_by(status="pending").count(),
        "processing": base_q.filter_by(status="processing").count(),
        "paused": base_q.filter_by(status="paused").count(),
        "completed": base_q.filter_by(status="completed").count(),
        "failed": base_q.filter_by(status="failed").count(),
        "cancelled": base_q.filter_by(status="cancelled").count(),
    }


def get_batch_items(db: Session, batch_id: str, offset: int, limit: int) -> list[OperationItem]:
    return db.query(OperationItem).filter_by(batch_id=batch_id).order_by(
        OperationItem.id).offset(offset).limit(limit).all()


def get_all_batch_items(db: Session, batch_id: str) -> list[OperationItem]:
    return db.query(OperationItem).filter_by(batch_id=batch_id).order_by(
        OperationItem.id).all()


def pause_batch(db: Session, batch_id: str) -> int:
    paused = db.query(OperationItem).filter_by(
        batch_id=batch_id, status="pending"
    ).update({"status": "paused", "updated_at": datetime.now(UTC)}, synchronize_session=False)
    db.commit()
    return paused


def resume_batch(db: Session, batch_id: str) -> int:
    resumed = db.query(OperationItem).filter_by(
        batch_id=batch_id, status="paused"
    ).update({"status": "pending", "updated_at": datetime.now(UTC)}, synchronize_session=False)
    db.commit()
    return resumed


def cancel_batch(db: Session, batch_id: str) -> int:
    cancelled = db.query(OperationItem).filter(
        OperationItem.batch_id == batch_id,
        OperationItem.status.in_(["pending", "processing", "paused"]),
    ).update({"status": "cancelled", "updated_at": datetime.now(UTC)}, synchronize_session=False)
    db.commit()
    return cancelled


def delete_batch(db: Session, batch_id: str) -> bool:
    batch = get_batch(db, batch_id)
    if not batch:
        return False
    db.query(OperationItem).filter_by(batch_id=batch_id).delete(synchronize_session=False)
    db.delete(batch)
    db.commit()
    return True


def get_batch_paused_counts(db: Session, batch_ids: list[str]) -> dict[str, int]:
    if not batch_ids:
        return {}
    rows = db.query(
        OperationItem.batch_id, func.count(OperationItem.id)
    ).filter(
        OperationItem.batch_id.in_(batch_ids),
        OperationItem.status == "paused"
    ).group_by(OperationItem.batch_id).all()
    return {row[0]: row[1] for row in rows}


def delete_old_batches(db: Session, days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    old_batches = db.query(OperationBatch).filter(
        OperationBatch.created_at < cutoff
    ).all()
    batch_ids = [b.batch_id for b in old_batches]
    if batch_ids:
        db.query(OperationItem).filter(
            OperationItem.batch_id.in_(batch_ids)
        ).delete(synchronize_session=False)
    deleted = 0
    for b in old_batches:
        db.delete(b)
        deleted += 1
    db.commit()
    return deleted


def list_batches(db: Session, entity_type: str = None, action: str = None,
                 modalidad: str = None, limit: int = 20,
                 offset: int = 0) -> tuple[int, list[OperationBatch]]:
    query = db.query(OperationBatch)
    if entity_type:
        query = query.filter(OperationBatch.entity_type == entity_type)
    if action:
        query = query.filter(OperationBatch.action == action)
    if modalidad:
        query = query.filter(OperationBatch.modalidad == modalidad)
    total = query.count()
    batches = query.order_by(OperationBatch.created_at.desc()).offset(offset).limit(limit).all()
    return total, batches


def get_operations_analytics(db: Session, modalidad: str = None, months: int = 12,
                             entity_type: str = None, action: str = None) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(days=months * 30)
    base_filters = [OperationBatch.created_at >= cutoff]
    if modalidad:
        base_filters.append(OperationBatch.modalidad == modalidad)

    monthly_batches = db.query(OperationBatch).filter(*base_filters)
    if entity_type:
        monthly_batches = monthly_batches.filter(OperationBatch.entity_type == entity_type)
    if action:
        monthly_batches = monthly_batches.filter(OperationBatch.action == action)

    raw_monthly = monthly_batches.all()

    base_metrics = {
        "users_created": 0, "users_deleted": 0,
        "categories_created": 0, "categories_deleted": 0,
        "courses_deleted": 0, "total_errors": 0,
    }

    months_data: dict[str, dict] = {}

    for b in raw_monthly:
        month = b.created_at.strftime("%Y-%m")
        if month not in months_data:
            months_data[month] = dict(base_metrics, month=month)

        m = months_data[month]
        m["total_errors"] += (b.failed or 0)
        key = f"{b.entity_type}_{b.action}"
        if key == "users_create":
            m["users_created"] += (b.completed or 0)
        elif key == "users_delete":
            m["users_deleted"] += (b.completed or 0)
        elif key == "categories_create":
            m["categories_created"] += (b.completed or 0)
        elif key == "categories_delete":
            m["categories_deleted"] += (b.completed or 0)
        elif key == "courses_delete":
            m["courses_deleted"] += (b.completed or 0)

    return sorted(months_data.values(), key=lambda m: m["month"])
