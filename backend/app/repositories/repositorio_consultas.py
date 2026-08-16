from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import QueryResult


def get_query(db: Session, task_id: str) -> QueryResult | None:
    return db.query(QueryResult).filter_by(task_id=task_id).first()


def create_query(
    db: Session, task_id: str, entity: str, params: dict, modalidad: str
) -> QueryResult:
    qr = QueryResult(
        task_id=task_id,
        entity=entity,
        params=params,
        status="pending",
        modalidad=modalidad,
    )
    db.add(qr)
    db.commit()
    return qr


def set_query_running(db: Session, task_id: str) -> QueryResult | None:
    qr = db.query(QueryResult).filter_by(task_id=task_id).first()
    if qr:
        qr.status = "running"
        qr.error_message = None
        qr.result_json = None
        qr.completed_at = None
        db.commit()
    return qr


def set_query_completed(
    db: Session, task_id: str, result_json, total_count: int
) -> QueryResult | None:
    qr = db.query(QueryResult).filter_by(task_id=task_id).first()
    if qr:
        qr.result_json = result_json
        qr.total_count = total_count
        qr.status = "completed"
        qr.completed_at = datetime.now(UTC)
        db.commit()
    return qr


def set_query_failed(db: Session, task_id: str, error_message: str) -> QueryResult | None:
    qr = db.query(QueryResult).filter_by(task_id=task_id).first()
    if qr:
        qr.status = "failed"
        qr.error_message = error_message[:500]
        qr.completed_at = datetime.now(UTC)
        db.commit()
    return qr


def delete_old_queries(db: Session, days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    deleted = (
        db.query(QueryResult)
        .filter(QueryResult.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
