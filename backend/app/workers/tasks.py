"""
Tareas asíncronas (Celery) para el procesamiento ETL.

Pipeline de 5 fases del Módulo de Novedades con checkpointing:
  FASE 1: Extract     — parsear Excel + consultar Moodle (solo GETs)
  FASE 2: Transform   — analizar en memoria, comparar cursos
  FASE 3: Structure   — ejecutar cambios estructurales (categorías + cursos)
  FASE 4: People      — crear usuarios y matricular docentes
  FASE 5: Reports     — generar CSVs y gráficos

Tras un crash, Celery reintenta la tarea y el checkpoint salta
las fases ya completadas, reanudando desde la fase fallida.
"""

import asyncio
import logging
import time
from typing import Dict

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.moodle import MoodleIntegration
from app.repositories.execution_repo import (
    clear_checkpoint,
    get_checkpoint,
    get_execution,
    mark_completed,
    mark_failed,
    mark_running,
    save_checkpoint,
    set_report_dir,
    update_progress,
    _should_pause,
)
from app.repositories.log_repo import save_error
from app.services.error_messages import translate_error
from app.services.etl import ETLService
from app.services.moodle import MoodleService
from app.services.reports import ReportService
from app.workers.phases.base import PhaseContext
from app.workers.phases.phase1_consult import ConsultPhase
from app.workers.phases.phase2_analyze import AnalyzePhase
from app.workers.phases.phase3_structure import StructurePhase
from app.workers.phases.phase4_people import PeoplePhase

logger = logging.getLogger(__name__)

PHASES = [ConsultPhase(), AnalyzePhase(), StructurePhase(), PeoplePhase()]
PHASE_NAMES = ["1", "2", "3", "4"]
PROGRESS_START = [0, 20, 40, 65]
PROGRESS_RESTORE = [12, 30, 52, 74]


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_etl_file(self, execution_id: int, file_path: str, semester: str) -> None:
    db = SessionLocal()
    start_time = time.monotonic()
    execution = None

    try:
        execution = get_execution(db, execution_id)
        if not execution:
            logger.exception(f"No se encontró la ejecución {execution_id}")
            return

        mark_running(db, execution_id)

        logger.info(f"Procesando archivo: {file_path}")
        etl_data = ETLService.process(file_path, execution.modalidad)

        moodle_config = settings.get_moodle_config(execution.modalidad or "")
        moodle_service = MoodleService(
            token=moodle_config["token"],
            base_url=moodle_config["url"],
            version=moodle_config["version"],
        )
        integration = MoodleIntegration(moodle_service)

        async def _run_phases() -> Dict[str, int]:
            try:
                return await _run_pipeline()
            finally:
                await moodle_service.close()

        async def _run_pipeline() -> Dict[str, int]:
            ctx = PhaseContext(
                db=db,
                execution_id=execution_id,
                execution=execution,
                mode=execution.mode,
                semester=semester,
                etl_data=etl_data,
                moodle_service=moodle_service,
                integration=integration,
            )

            checkpoint = get_checkpoint(db, execution_id) or {}

            for i, phase in enumerate(PHASES):
                phase_name = PHASE_NAMES[i]

                if _should_pause(db, execution_id):
                    update_progress(db, execution_id, PROGRESS_RESTORE[i - 1] if i > 0 else 12,
                                    f"FASE {phase_name} pausada")
                    logger.info(f"FASE {phase_name}: pausada por el usuario")
                    return ctx.metrics

                if phase_name in checkpoint:
                    _restore_checkpoint(ctx, checkpoint[phase_name], phase_name)
                    retry_count = _inc_retry_count(db, execution_id)
                    retry_label = f" (reintento {retry_count})" if retry_count > 0 else ""
                    update_progress(db, execution_id, PROGRESS_RESTORE[i],
                                    f"FASE {phase_name} restaurada desde checkpoint{retry_label}")
                    logger.info(f"FASE {phase_name}: restaurada desde checkpoint (reintento {retry_count})")
                else:
                    await phase.run(ctx)
                    _save_phase_checkpoint(db, execution_id, ctx, phase_name)
                    logger.info(f"FASE {phase_name}: completada, checkpoint guardado")

                    if phase_name == "2" and ctx.mode in ("courses", "both") and not _is_delete_confirmed(db, execution_id):
                        to_delete_count = len(ctx.comparison.get("to_delete", []))
                        if to_delete_count > settings.MAX_AUTO_DELETE_COURSES:
                            _require_review(db, execution_id, ctx)
                            return ctx.metrics

            return ctx.metrics

        metrics = asyncio.run(_run_phases())

        if _get_execution_status(db, execution_id) == "review_required":
            logger.info(f"Ejecución {execution_id}: en espera de confirmación de eliminación masiva")
            return

        update_progress(db, execution_id, 85, "Generando reportes…", step=5)
        report_ok = True
        try:
            report_dir = ReportService.generate_all(execution_id, db)
            set_report_dir(db, execution_id, report_dir)
            logger.info(f"Reportes generados en: {report_dir}")
        except Exception as e:
            logger.exception(f"Error generando reportes: {e}")
            save_error(db, execution_id, "critical", "", translate_error(e))
            report_ok = False

        update_progress(db, execution_id, 95, "Finalizando…")
        mark_completed(
            db, execution_id, metrics,
            errors_count=metrics.get("total_errors", 0),
            duration_seconds=time.monotonic() - start_time,
        )
        clear_checkpoint(db, execution_id)
        update_progress(db, execution_id, 100, "Ejecución completada")

        status_label = "con reportes" if report_ok else "sin reportes"
        logger.info(f"Ejecución {execution_id} completada exitosamente ({status_label})")

    except Exception as e:
        logger.exception(f"Error crítico en ejecución {execution_id}: {e}")
        try:
            db.rollback()
            if execution:
                save_error(db, execution_id, "critical", "", translate_error(e))
                mark_failed(db, execution_id, time.monotonic() - start_time)
        except Exception as db_error:
            logger.exception(f"No se pudo actualizar el estado fallido: {db_error}")
    finally:
        db.close()


def _save_phase_checkpoint(db, eid, ctx: PhaseContext, phase_name: str):
    if phase_name == "1":
        save_checkpoint(db, eid, "1", {
            "cat_idnumbers": list(ctx.existing_cat_idnumbers),
            "courses": ctx.existing_courses,
            "username_map": ctx.username_map,
            "courses_with_teacher": list(ctx.courses_with_teacher),
        })
    elif phase_name == "2":
        save_checkpoint(db, eid, "2", {
            "comparison": _serialize_comparison(ctx.comparison),
            "missing_categories": ctx.missing_categories,
            "users_to_create": ctx.users_to_create,
            "resolved_enrolments": ctx.resolved_enrolments,
            "re_upload": ctx.re_upload,
        })
    elif phase_name == "3":
        save_checkpoint(db, eid, "3", {
            "metrics": dict(ctx.metrics),
            "username_map": ctx.username_map,
            "structure_progress": getattr(ctx, "structure_progress", {}),
        })
    elif phase_name == "4":
        save_checkpoint(db, eid, "4", {
            "metrics": dict(ctx.metrics),
            "username_map": ctx.username_map,
            "people_progress": getattr(ctx, "people_progress", {}),
        })


def _restore_checkpoint(ctx: PhaseContext, data: dict, phase_name: str):
    if phase_name == "1":
        ctx.existing_cat_idnumbers = set(data.get("cat_idnumbers", []))
        ctx.existing_courses = data.get("courses", [])
        ctx.username_map = data.get("username_map", {})
        ctx.courses_with_teacher = set(data.get("courses_with_teacher", []))
    elif phase_name == "2":
        ctx.comparison = data.get("comparison", {})
        ctx.missing_categories = data.get("missing_categories", [])
        ctx.users_to_create = data.get("users_to_create", [])
        ctx.resolved_enrolments = data.get("resolved_enrolments", [])
        ctx.re_upload = data.get("re_upload", False)
    elif phase_name == "3":
        ctx.metrics.update(data.get("metrics", {}))
        ctx.username_map.update(data.get("username_map", {}))
        ctx.structure_progress = data.get("structure_progress", {})
    elif phase_name == "4":
        ctx.metrics.update(data.get("metrics", {}))
        ctx.username_map.update(data.get("username_map", {}))
        ctx.people_progress = data.get("people_progress", {})


def _serialize_comparison(comparison: dict) -> dict:
    """Convierte sets a listas para serialización JSON."""
    result = {}
    for k, v in comparison.items():
        if k == "logs":
            result[k] = v
        elif isinstance(v, set):
            result[k] = list(v)
        elif isinstance(v, list):
            result[k] = v
        else:
            result[k] = v
    return result


def _is_delete_confirmed(db, execution_id: int) -> bool:
    """Verifica si la ejecución ya fue confirmada para eliminación masiva."""
    from app.db.models import Execution
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if not ex or not ex.phase_checkpoint:
        return False
    return ex.phase_checkpoint.get("delete_confirmed", False)


def _get_execution_status(db, execution_id: int) -> str:
    """Retorna el status actual de una ejecución."""
    from app.db.models import Execution
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    return ex.status if ex else ""


def _require_review(db, execution_id: int, ctx):
    """Marca la ejecución como pendiente de revisión por eliminación masiva."""
    from app.db.models import Execution
    from sqlalchemy.orm.attributes import flag_modified
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if ex:
        to_delete_count = len(ctx.comparison.get("to_delete", []))
        ex.status = "review_required"
        ex.current_phase = f"Revisión requerida: {to_delete_count} cursos a eliminar"
        ex.progress_pct = 30
        ex.metrics = {
            **(ex.metrics or {}),
            "pending_delete_count": to_delete_count,
        }
        if ex.phase_checkpoint is None:
            ex.phase_checkpoint = {}
        ex.phase_checkpoint["delete_review"] = {
            "to_delete_count": to_delete_count,
            "to_create_count": len(ctx.comparison.get("to_create", [])),
            "threshold": settings.MAX_AUTO_DELETE_COURSES,
        }
        flag_modified(ex, "phase_checkpoint")
        db.commit()
        logger.warning(
            f"Ejecución {execution_id}: {to_delete_count} cursos a eliminar "
            f"(umbral: {settings.MAX_AUTO_DELETE_COURSES}). "
            f"Requiere confirmación explícita."
        )


def _inc_retry_count(db, execution_id: int) -> int:
    """Incrementa y retorna el contador de reintentos almacenado en el checkpoint."""
    from app.db.models import Execution
    from sqlalchemy.orm.attributes import flag_modified
    ex = db.query(Execution).filter(Execution.id == execution_id).first()
    if not ex:
        return 0
    if ex.phase_checkpoint is None:
        ex.phase_checkpoint = {}
    count = ex.phase_checkpoint.get("_retry_count", 0) + 1
    ex.phase_checkpoint["_retry_count"] = count
    flag_modified(ex, "phase_checkpoint")
    db.commit()
    return count
