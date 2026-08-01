from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.db.models import ErrorLog, Execution


def get_execution(db: Session, execution_id: int) -> Optional[Execution]:
    return db.query(Execution).filter(Execution.id == execution_id).first()


def create_execution(db: Session, filename: str, semester: str, mode: str,
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


def atomic_mark_queued(db: Session, execution_id: int, task_id: str, allowed_statuses: tuple) -> bool:
    result = db.execute(
        sql_text(
            "UPDATE executions SET status = 'queued', started_at = :now, celery_task_id = :task_id "
            "WHERE id = :id AND status IN :allowed_statuses"
        ),
        {"now": datetime.now(timezone.utc), "task_id": task_id, "id": execution_id,
         "allowed_statuses": allowed_statuses},
    )
    db.commit()
    return result.rowcount > 0


def update_progress(db: Session, execution_id: int, pct: float, phase: str = None, step: int = None) -> None:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        if phase is not None:
            execution.current_phase = phase
        execution.progress_pct = pct
        execution.progress_updated_at = datetime.now(timezone.utc)
        if step is not None:
            execution.current_step = step
        db.commit()


def touch_heartbeat(db: Session, execution_id: int) -> None:
    """Actualiza solo progress_updated_at sin cambiar porcentaje ni mensaje."""
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.progress_updated_at = datetime.now(timezone.utc)
        db.commit()


def mark_running(db: Session, execution_id: int) -> Optional[Execution]:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)
        execution.progress_pct = 0
        db.commit()
    return execution


def mark_completed(db: Session, execution_id: int, metrics: dict,
                   errors_count: int, duration_seconds: float) -> Optional[Execution]:
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


def mark_failed(db: Session, execution_id: int, duration_seconds: float) -> Optional[Execution]:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.status = "failed"
        execution.completed_at = datetime.now(timezone.utc)
        execution.duration_seconds = round(duration_seconds, 2)
        db.commit()
    return execution


def delete_execution(db: Session, execution_id: int) -> None:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        db.delete(execution)
        db.commit()


def list_executions(db: Session, semester: str = None, status: str = None, mode: str = None,
                    moodle_version: str = None, modalidad: str = None,
                    limit: int = 20, offset: int = 0) -> Tuple[int, List[Execution]]:
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


def get_execution_errors(db: Session, execution_id: int, limit: int, offset: int) -> List[ErrorLog]:
    return (
        db.query(ErrorLog)
        .filter(ErrorLog.execution_id == execution_id)
        .order_by(ErrorLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def set_report_dir(db: Session, execution_id: int, report_dir: str) -> None:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.report_dir = report_dir
        db.commit()


def is_reupload(db: Session, semester: str, modalidad: str, exclude_id: int) -> bool:
    return db.query(Execution).filter(
        Execution.semester == semester,
        Execution.modalidad == modalidad,
        Execution.status == "completed",
        Execution.id != exclude_id,
    ).first() is not None


def delete_old_pending_executions(db: Session, hours: int = 24) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    old = db.query(Execution).filter(
        Execution.status == "pending",
        Execution.created_at < cutoff,
    ).all()
    if not old:
        return 0
    for ex in old:
        db.delete(ex)
    db.commit()
    return len(old)


def save_checkpoint(db: Session, execution_id: int, phase: str, data: dict) -> None:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        if execution.phase_checkpoint is None:
            execution.phase_checkpoint = {}
        execution.phase_checkpoint[phase] = data
        flag_modified(execution, "phase_checkpoint")
        db.commit()


def get_checkpoint(db: Session, execution_id: int) -> Optional[Dict]:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution or not execution.phase_checkpoint:
        return None
    return dict(execution.phase_checkpoint)


def set_chord_active(db: Session, execution_id: int, minutes: int = None) -> None:
    """Marca un chord de fase como activo hasta una fecha de expiración.

    El sweeper ``recover_stuck_phase`` usa esta marca para relanzar una fase
    cuyo chord quedó huérfano (worker caído, callback nunca ejecutado).
    """
    minutes = settings.CHORD_ACTIVE_MINUTES if minutes is None else minutes
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    save_checkpoint(db, execution_id, "chord_active", expires.isoformat())


def clear_chord_active(db: Session, execution_id: int) -> None:
    """Limpia la marca de chord activo (al iniciar el callback de la fase)."""
    save_checkpoint(db, execution_id, "chord_active", None)


def clear_checkpoint(db: Session, execution_id: int) -> None:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        execution.phase_checkpoint = None
        flag_modified(execution, "phase_checkpoint")
        db.commit()


def pause_execution(db: Session, execution_id: int) -> Tuple[bool, str]:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution or execution.status != "running":
        return False, ""
    task_id = execution.celery_task_id or ""
    execution.status = "paused"
    if " (pausado)" not in (execution.current_phase or ""):
        execution.current_phase = f"{execution.current_phase or ''} (pausado)"
    db.commit()
    return True, task_id


def increment_metric(db: Session, execution_id: int, metric_name: str, delta: int = 1) -> None:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if execution:
        metrics = execution.metrics or {}
        metrics[metric_name] = metrics.get(metric_name, 0) + delta
        execution.metrics = metrics
        flag_modified(execution, "metrics")
        db.flush()


def should_pause(db: Session, execution_id: int) -> bool:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    return execution is not None and execution.status == "paused"


def cancel_execution(db: Session, execution_id: int) -> Tuple[bool, str]:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution or execution.status not in ("running", "paused", "queued"):
        return False, ""
    task_id = execution.celery_task_id or ""
    execution.status = "cancelled"
    execution.current_phase = f"{execution.current_phase or ''} (cancelado)"
    execution.completed_at = datetime.now(timezone.utc)
    execution.duration_seconds = round(
        (datetime.now(timezone.utc) - execution.started_at).total_seconds()
    ) if execution.started_at else 0
    db.commit()
    return True, task_id


def should_cancel(db: Session, execution_id: int) -> bool:
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    return execution is not None and execution.status == "cancelled"
