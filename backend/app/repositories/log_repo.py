from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import ErrorLog, ExecutionLog


def save_log(db: Session, execution_id: int, phase: str, action: str,
             identifier: str = None, detail: dict = None) -> None:
    log = ExecutionLog(
        execution_id=execution_id,
        phase=phase,
        action=action,
        identifier=identifier,
        detail=detail or {},
    )
    db.add(log)
    db.flush()


def save_error(db: Session, execution_id: int, err_type: str,
               identifier: str = None, message: str = None) -> None:
    error = ErrorLog(
        execution_id=execution_id,
        type=err_type,
        identifier=identifier,
        message=message,
    )
    db.add(error)
    db.flush()


def get_execution_logs(db: Session, execution_id: int, limit: int = 100, offset: int = 0) -> List[ExecutionLog]:
    return db.query(ExecutionLog).filter(
        ExecutionLog.execution_id == execution_id
    ).order_by(ExecutionLog.created_at.desc()).offset(offset).limit(limit).all()
