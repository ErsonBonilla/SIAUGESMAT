from datetime import datetime, timezone

from app.db.models import ErrorLog, ExecutionLog


def save_log(db, execution_id: int, phase: str, action: str,
             identifier: str = None, detail: dict = None):
    log = ExecutionLog(
        execution_id=execution_id,
        phase=phase,
        action=action,
        identifier=identifier,
        detail=detail or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)


def save_error(db, execution_id: int, err_type: str,
               identifier: str = None, message: str = None):
    error = ErrorLog(
        execution_id=execution_id,
        type=err_type,
        identifier=identifier,
        message=message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(error)


def get_execution_logs(db, execution_id: int):
    return db.query(ExecutionLog).filter(
        ExecutionLog.execution_id == execution_id
    ).all()
