from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db.models import QueryResult


def get_query(db, task_id: str) -> Optional[QueryResult]:
    return db.query(QueryResult).filter_by(task_id=task_id).first()


def create_query(db, task_id: str, entity: str, params: dict,
                 modalidad: str) -> QueryResult:
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


def set_query_running(db, task_id: str):
    qr = db.query(QueryResult).filter_by(task_id=task_id).first()
    if qr:
        qr.status = "running"
        qr.error_message = None
        qr.result_json = None
        qr.completed_at = None
        db.commit()
    return qr


def set_query_completed(db, task_id: str, result_json, total_count: int):
    qr = db.query(QueryResult).filter_by(task_id=task_id).first()
    if qr:
        qr.result_json = result_json
        qr.total_count = total_count
        qr.status = "completed"
        qr.completed_at = datetime.now(timezone.utc)
        db.commit()


def set_query_failed(db, task_id: str, error_message: str):
    qr = db.query(QueryResult).filter_by(task_id=task_id).first()
    if qr:
        qr.status = "failed"
        qr.error_message = error_message[:500]
        qr.completed_at = datetime.now(timezone.utc)
        db.commit()


def delete_old_queries(db, days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted = db.query(QueryResult).filter(
        QueryResult.created_at < cutoff
    ).delete(synchronize_session=False)
    db.commit()
    return deleted
