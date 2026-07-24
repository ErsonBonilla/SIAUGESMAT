from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.db.models import ErrorLog, Execution


def get_execution(db, execution_id: int) -> Optional[Execution]:
    return db.query(Execution).filter(Execution.id == execution_id).first()


def create_execution(db, filename: str, semester: str, mode: str,
                     modalidad: str, moodle_version: str) -> Execution:
    execution = Execution(
        filename=filename,
        semester=semester,
        mode=mode,
        status="pending",
        moodle_version=moodle_version,
        modalidad=modalidad,
        created_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def mark_queued(db, execution_id: int):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.status = "queued"
        execution.started_at = datetime.now(timezone.utc)
        db.commit()
    return execution


def update_progress(db, execution_id: int, pct: float, phase: str, step: int = None):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.current_phase = phase
        execution.progress_pct = pct
        if step is not None:
            execution.current_step = step
        db.commit()


def mark_running(db, execution_id: int):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)
        execution.progress_pct = 0
        db.commit()
    return execution


def mark_completed(db, execution_id: int, metrics: dict,
                   errors_count: int, duration_seconds: float):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.status = "completed"
        execution.metrics = metrics
        execution.errors_count = errors_count
        execution.completed_at = datetime.now(timezone.utc)
        execution.duration_seconds = round(duration_seconds, 2)
        execution.current_phase = "Procesamiento completado"
        execution.progress_pct = 100
        db.commit()
    return execution


def mark_failed(db, execution_id: int, duration_seconds: float):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.status = "failed"
        execution.completed_at = datetime.now(timezone.utc)
        execution.duration_seconds = round(duration_seconds, 2)
        db.commit()
    return execution


def delete_execution(db, execution_id: int):
    db.query(ErrorLog).filter(ErrorLog.execution_id == execution_id).delete()
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        db.delete(execution)
        db.commit()


def list_executions(db, semester: str = None, status: str = None, mode: str = None,
                    moodle_version: str = None, modalidad: str = None,
                    limit: int = 20, offset: int = 0) -> tuple[int, List[Execution]]:
    query = db.query(Execution)
    if semester:
        query = query.filter(Execution.semester == semester)
    if status:
        query = query.filter(Execution.status == status)
    if mode:
        query = query.filter(Execution.mode == mode)
    if moodle_version:
        query = query.filter(Execution.moodle_version == moodle_version)
    if modalidad:
        query = query.filter(Execution.modalidad == modalidad.upper())
    total = query.count()
    executions = query.order_by(Execution.created_at.desc()).offset(offset).limit(limit).all()
    return total, executions


def get_execution_errors(db, execution_id: int, limit: int, offset: int) -> List[ErrorLog]:
    return (
        db.query(ErrorLog)
        .filter(ErrorLog.execution_id == execution_id)
        .order_by(ErrorLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def set_report_dir(db, execution_id: int, report_dir: str):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.report_dir = report_dir
        db.commit()


def is_reupload(db, semester: str, modalidad: str, exclude_id: int) -> bool:
    return db.query(Execution).filter(
        Execution.semester == semester,
        Execution.modalidad == modalidad,
        Execution.status == "completed",
        Execution.id != exclude_id,
    ).first() is not None


def delete_old_pending_executions(db, hours: int = 24) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    old = db.query(Execution).filter(
        Execution.status == "pending",
        Execution.created_at < cutoff,
    ).all()
    if not old:
        return 0
    for ex in old:
        db.query(ErrorLog).filter(ErrorLog.execution_id == ex.id).delete()
        db.delete(ex)
    db.commit()
    return len(old)


def save_checkpoint(db, execution_id: int, phase: str, data: dict):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        if execution.phase_checkpoint is None:
            execution.phase_checkpoint = {}
        execution.phase_checkpoint[phase] = data
        db.commit()


def get_checkpoint(db, execution_id: int):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution or not execution.phase_checkpoint:
        return None
    return dict(execution.phase_checkpoint)


def clear_checkpoint(db, execution_id: int):
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.phase_checkpoint = None
        db.commit()
