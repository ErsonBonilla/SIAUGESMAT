"""
Tareas asíncronas (Celery) para el procesamiento ETL.

Pipeline de 4 fases del Módulo de Novedades con checkpointing:
  FASE 1: ConsultPhase  — consultar Moodle (solo GETs)
  FASE 2: AnalyzePhase  — analizar en memoria, comparar cursos
  FASE 3: ExecutePhase  — ejecutar cambios en Moodle
  FASE 4: generar reportes

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
)
from app.repositories.log_repo import save_error
from app.services.error_messages import translate_error
from app.services.etl import ETLService
from app.services.moodle import MoodleService
from app.services.reports import ReportService
from app.workers.phases.base import PhaseContext
from app.workers.phases.phase1_consult import ConsultPhase
from app.workers.phases.phase2_analyze import AnalyzePhase
from app.workers.phases.phase3_execute import ExecutePhase

logger = logging.getLogger(__name__)

PHASES = [ConsultPhase(), AnalyzePhase(), ExecutePhase()]
PHASE_NAMES = ["1", "2", "3"]


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

                if phase_name in checkpoint:
                    _restore_checkpoint(ctx, checkpoint[phase_name], phase_name)
                    update_progress(db, execution_id, [14, 24, 26][i],
                                    f"FASE {phase_name} restaurada desde checkpoint")
                    logger.info(f"FASE {phase_name}: restaurada desde checkpoint")
                else:
                    await phase.run(ctx)
                    _save_phase_checkpoint(db, execution_id, ctx, phase_name)
                    logger.info(f"FASE {phase_name}: completada, checkpoint guardado")

            return ctx.metrics

        metrics = asyncio.run(_run_phases())
        update_progress(db, execution_id, 92, "Guardando resultados…")

        mark_completed(
            db, execution_id, metrics,
            errors_count=metrics.get("total_errors", 0),
            duration_seconds=time.monotonic() - start_time,
        )
        clear_checkpoint(db, execution_id)

        update_progress(db, execution_id, 94, "Generando reportes…", step=4)
        try:
            report_dir = ReportService.generate_all(execution_id, db)
            set_report_dir(db, execution_id, report_dir)
            update_progress(db, execution_id, 99, "Reportes generados")
            logger.info(f"Reportes generados en: {report_dir}")
        except Exception as e:
            logger.exception(f"Error generando reportes: {e}")

        logger.info(f"Ejecución {execution_id} completada exitosamente")

    except Exception as e:
        logger.exception(f"Error crítico en ejecución {execution_id}: {e}")
        try:
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
            "phase3_progress": getattr(ctx, "phase3_progress", {}),
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
        ctx.phase3_progress = data.get("phase3_progress", {})


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
