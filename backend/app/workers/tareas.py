import logging
import time

from app.celery_app import celery_app
from app.core.config import settings
from app.db.sesion import SessionLocal
from app.integrations.integracion_moodle import IntegracionMoodle
from app.repositories.repositorio_ejecuciones import (
    actualizar_progreso,
    debe_cancelarse,
    debe_pausarse,
    marcar_en_ejecucion,
    marcar_fallido,
    obtener_checkpoint,
    obtener_ejecucion,
)
from app.repositories.repositorio_registros import guardar_error
from app.services.fabrica_moodle import obtener_servicio_moodle
from app.services.mensajes_error import traducir_error
from app.services.proceso_etl import ServicioETL
from app.workers.phases.base import ContextoFase, ErrorMoodleSobrecargado
from app.workers.phases.fase1_consulta import FaseConsulta
from app.workers.phases.fase2_analisis import FaseAnalisis
from app.workers.phases.orquestador import (
    _es_eliminacion_confirmada,
    _guardar_checkpoint_fase,
    _guardar_datos_fase2_en_checkpoint,
    _incrementar_conteo_reintentos,
    _requerir_revision,
    _restaurar_checkpoint,
    _restaurar_checkpoint_progreso,
    procesar_fase_etl,
)
from app.workers.utilidades import ejecutar_moodle_async

logger = logging.getLogger(__name__)

PHASES = [FaseConsulta(), FaseAnalisis()]
PHASE_NAMES = ["1", "2"]
PROGRESS_START = [0, 20]
PROGRESS_RESTORE = [12, 30]


@celery_app.task(
    name="app.workers.tasks.process_etl_file",
    bind=True,
    autoretry_for=(ErrorMoodleSobrecargado,),
    max_retries=10,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    soft_time_limit=25200,
    time_limit=28800,
)
def procesar_archivo_etl(self, execution_id: int, file_path: str, semester: str) -> None:
    db = SessionLocal()
    start_time = time.monotonic()
    execution = None

    try:
        execution = obtener_ejecucion(db, execution_id)
        if not execution:
            logger.warning(f"No se encontró la ejecución {execution_id}")
            return

        if execution.estado in ("cancelled", "paused", "review_required"):
            logger.info(f"Ejecución {execution_id} {execution.estado}, no se procesa")
            return

        marcar_en_ejecucion(db, execution_id)

        logger.info(f"Procesando archivo: {file_path}")
        etl_data = ServicioETL.procesar(file_path, execution.modalidad)

        moodle_service = obtener_servicio_moodle(execution.modalidad or "")
        integration = IntegracionMoodle(moodle_service)

        async def _ejecutar_pipeline() -> dict[str, int]:
            # Refrescar execution para PhaseContext
            current_exec = obtener_ejecucion(db, execution_id) or execution
            ctx = ContextoFase(
                db=db,
                ejecucion_id=execution_id,
                ejecucion=current_exec,
                modo=current_exec.modo,
                semestre=semester,
                datos_etl=etl_data,
                servicio_moodle=moodle_service,
                integracion=integration,
            )

            checkpoint = obtener_checkpoint(db, execution_id) or {}

            for i, phase in enumerate(PHASES):
                nombre_fase = PHASE_NAMES[i]

                if debe_cancelarse(db, execution_id):
                    actualizar_progreso(
                        db,
                        execution_id,
                        PROGRESS_RESTORE[i - 1] if i > 0 else 12,
                        f"FASE {nombre_fase} cancelada",
                    )
                    logger.info(f"FASE {nombre_fase}: cancelada por el usuario")
                    return ctx.metricas

                if debe_pausarse(db, execution_id):
                    actualizar_progreso(
                        db,
                        execution_id,
                        PROGRESS_RESTORE[i - 1] if i > 0 else 12,
                        f"FASE {nombre_fase} pausada",
                    )
                    logger.info(f"FASE {nombre_fase}: pausada por el usuario")
                    return ctx.metricas

                if nombre_fase in checkpoint:
                    _restaurar_checkpoint(ctx, checkpoint[nombre_fase], nombre_fase)
                    retry_count = _incrementar_conteo_reintentos(db, execution_id)
                    retry_label = f" (reintento {retry_count})" if retry_count > 0 else ""
                    actualizar_progreso(
                        db,
                        execution_id,
                        PROGRESS_RESTORE[i],
                        f"FASE {nombre_fase} restaurada desde checkpoint{retry_label}",
                    )
                    logger.info(
                        f"FASE {nombre_fase}: restaurada desde checkpoint (reintento {retry_count})"
                    )
                else:
                    progress_key = f"{nombre_fase}_progress"
                    if progress_key in checkpoint:
                        _restaurar_checkpoint_progreso(ctx, checkpoint[progress_key], nombre_fase)
                        logger.info(f"FASE {nombre_fase}: progreso parcial restaurado")
                    await phase.ejecutar(ctx)
                    _guardar_checkpoint_fase(db, execution_id, ctx, nombre_fase)
                    logger.info(f"FASE {nombre_fase}: completada, checkpoint guardado")

                    if (
                        nombre_fase == "2"
                        and ctx.modo in ("courses", "both")
                        and not _es_eliminacion_confirmada(db, execution_id)
                    ):
                        to_delete_count = len(ctx.comparacion.get("to_delete", []))
                        if to_delete_count > settings.MAX_AUTO_DELETE_COURSES:
                            _requerir_revision(db, execution_id, ctx)
                            return ctx.metricas

            return ctx.metricas

        metrics = ejecutar_moodle_async(moodle_service, _ejecutar_pipeline())

        # Fresco: consultar estado actual de BD
        current_exec = obtener_ejecucion(db, execution_id)

        if not current_exec:
            return

        if current_exec.estado in ("cancelled", "paused"):
            logger.info(
                f"Ejecución {execution_id}: {current_exec.estado} después de fases 1-2, no se lanza Fase 3"
            )
            return

        if current_exec.estado == "review_required":
            logger.info(
                f"Ejecución {execution_id}: en espera de confirmación de eliminación masiva"
            )
            return

        if current_exec.estado == "completed":
            logger.info(
                f"Ejecución {execution_id}: ya completada por chord callbacks, no se relanza"
            )
            return

            # Save context for Phase 3 subtask orchestration
        phase2_data = obtener_checkpoint(db, execution_id) or {}
        _guardar_datos_fase2_en_checkpoint(
            db,
            execution_id,
            etl_data,
            metrics,
            phase2_data,
            current_exec.modalidad,
            current_exec.modo,
        )

        actualizar_progreso(db, execution_id, 32, "Preparando subtareas…", paso=3)
        logger.info(f"Ejecución {execution_id}: lanzando FASE 3 como subtareas")
        procesar_fase_etl.delay(execution_id, "3")

    except ErrorMoodleSobrecargado:
        raise
    except Exception as e:
        logger.exception(f"Error crítico en ejecución {execution_id}: {e}")
        try:
            db.rollback()
            if execution:
                guardar_error(db, execution_id, "critical", None, traducir_error(e))
            marcar_fallido(db, execution_id, time.monotonic() - start_time)
        except Exception as db_error:
            logger.exception(f"No se pudo actualizar el estado fallido: {db_error}")
    finally:
        db.close()
