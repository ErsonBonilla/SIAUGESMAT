import logging
import time
from typing import Dict

from app.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.moodle import MoodleIntegration
from app.repositories.execution_repo import (
    get_checkpoint,
    get_execution,
    mark_failed,
    mark_running,
    should_cancel,
    should_pause,
    update_progress,
)
from app.repositories.log_repo import save_error
from app.services.error_messages import translate_error
from app.services.etl import ETLService
from app.services.moodle_factory import get_moodle_service
from app.workers.phases.base import MoodleOverloadedError, PhaseContext
from app.workers.phases.orchestrator import (
    _inc_retry_count,
    _is_delete_confirmed,
    _require_review,
    _restore_checkpoint,
    _restore_progress_checkpoint,
    _save_phase_2_data_to_checkpoint,
    _save_phase_checkpoint,
    process_etl_phase,
)
from app.workers.phases.phase1_consult import ConsultPhase
from app.workers.phases.phase2_analyze import AnalyzePhase
from app.workers.utils import run_moodle_async

logger = logging.getLogger(__name__)

PHASES = [ConsultPhase(), AnalyzePhase()]
PHASE_NAMES = ["1", "2"]
PROGRESS_START = [0, 20]
PROGRESS_RESTORE = [12, 30]


@celery_app.task(bind=True, autoretry_for=(MoodleOverloadedError,), max_retries=10,
                  default_retry_delay=60, retry_backoff=True, retry_backoff_max=600, retry_jitter=True,
                  soft_time_limit=25200, time_limit=28800)
def process_etl_file(self, execution_id: int, file_path: str, semester: str) -> None:
    db = SessionLocal()
    start_time = time.monotonic()
    execution = None

    try:
        execution = get_execution(db, execution_id)
        if not execution:
            logger.exception(f"No se encontró la ejecución {execution_id}")
            return

        if execution.status in ("cancelled", "paused", "review_required"):
            logger.info(f"Ejecución {execution_id} {execution.status}, no se procesa")
            return

        mark_running(db, execution_id)

        logger.info(f"Procesando archivo: {file_path}")
        etl_data = ETLService.process(file_path, execution.modalidad)

        moodle_service = get_moodle_service(execution.modalidad or "")
        integration = MoodleIntegration(moodle_service)

        async def _run_pipeline() -> Dict[str, int]:
            # Refrescar execution para PhaseContext
            current_exec = get_execution(db, execution_id) or execution
            ctx = PhaseContext(
                db=db,
                execution_id=execution_id,
                execution=current_exec,
                mode=current_exec.mode,
                semester=semester,
                etl_data=etl_data,
                moodle_service=moodle_service,
                integration=integration,
            )

            checkpoint = get_checkpoint(db, execution_id) or {}

            for i, phase in enumerate(PHASES):
                phase_name = PHASE_NAMES[i]

                if should_cancel(db, execution_id):
                    update_progress(db, execution_id, PROGRESS_RESTORE[i - 1] if i > 0 else 12,
                                    f"FASE {phase_name} cancelada")
                    logger.info(f"FASE {phase_name}: cancelada por el usuario")
                    return ctx.metrics

                if should_pause(db, execution_id):
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
                    progress_key = f"{phase_name}_progress"
                    if progress_key in checkpoint:
                        _restore_progress_checkpoint(ctx, checkpoint[progress_key], phase_name)
                        logger.info(f"FASE {phase_name}: progreso parcial restaurado")
                    await phase.run(ctx)
                    _save_phase_checkpoint(db, execution_id, ctx, phase_name)
                    logger.info(f"FASE {phase_name}: completada, checkpoint guardado")

                    if phase_name == "2" and ctx.mode in ("courses", "both") and not _is_delete_confirmed(db, execution_id):
                        to_delete_count = len(ctx.comparison.get("to_delete", []))
                        if to_delete_count > settings.MAX_AUTO_DELETE_COURSES:
                            _require_review(db, execution_id, ctx)
                            return ctx.metrics

            return ctx.metrics

        metrics = run_moodle_async(moodle_service, _run_pipeline())

        # Fresco: consultar estado actual de BD
        current_exec = get_execution(db, execution_id)

        if not current_exec:
            return

        if current_exec.status in ("cancelled", "paused"):
            logger.info(f"Ejecución {execution_id}: {current_exec.status} después de fases 1-2, no se lanza Fase 3")
            return

        if current_exec.status == "review_required":
            logger.info(f"Ejecución {execution_id}: en espera de confirmación de eliminación masiva")
            return

        if current_exec.status == "completed":
            logger.info(f"Ejecución {execution_id}: ya completada por chord callbacks, no se relanza")
            return

        # Save context for Phase 3 subtask orchestration
        phase2_data = get_checkpoint(db, execution_id) or {}
        _save_phase_2_data_to_checkpoint(db, execution_id, etl_data, metrics, phase2_data, current_exec.modalidad, current_exec.mode)

        update_progress(db, execution_id, 32, "Preparando subtareas…", step=3)
        logger.info(f"Ejecución {execution_id}: lanzando FASE 3 como subtareas")
        process_etl_phase.delay(execution_id, "3")

    except MoodleOverloadedError:
        raise
    except Exception as e:
        logger.exception(f"Error crítico en ejecución {execution_id}: {e}")
        try:
            db.rollback()
            if execution:
                save_error(db, execution_id, "critical", None, translate_error(e))
            mark_failed(db, execution_id, time.monotonic() - start_time)
        except Exception as db_error:
            logger.exception(f"No se pudo actualizar el estado fallido: {db_error}")
    finally:
        db.close()
