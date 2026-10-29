"""
Tareas periódicas de limpieza automática.

Ejecutadas por Celery Beat según el `beat_schedule` configurado
en `celery_app.py`. No se ejecutan bajo demanda.
"""

import logging
from datetime import UTC, datetime, timedelta

from app.celery_app import celery_app
from app.core.config import settings
from app.db.modelos import Ejecucion
from app.db.sesion import SessionLocal
from app.repositories.repositorio_ejecuciones import eliminar_ejecuciones_pendientes_antiguas

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.cleanup_tasks.cleanup_pending_executions")
def limpiar_ejecuciones_pendientes():
    """Elimina ejecuciones en estado 'pending' con más de 24 horas de antigüedad."""
    db = SessionLocal()
    try:
        deleted = eliminar_ejecuciones_pendientes_antiguas(db, hours=24)
        if deleted:
            logger.info(f"Limpieza automática: {deleted} ejecuciones pending eliminadas")
    except Exception:
        logger.exception("Error en limpieza automática de ejecuciones pending")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="app.workers.cleanup_tasks.cleanup_stuck_executions")
def limpiar_ejecuciones_atascadas():
    """Marca como 'failed' ejecuciones 'running'/'queued' sin cambios por más de 6h."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(UTC)
        stuck = (
            db.query(Ejecucion)
            .filter(
                Ejecucion.estado.in_(["running", "queued"]),
            )
            .all()
        )
        count = 0
        for ex in stuck:
            ref_dt = ex.progreso_actualizado_en or ex.iniciado_en or ex.creado_en
            if ref_dt is None:
                continue
            if ref_dt.tzinfo is None:
                ref_dt = ref_dt.replace(tzinfo=UTC)
            age = (cutoff - ref_dt).total_seconds()
            if age > settings.STUCK_EXECUTION_TIMEOUT:
                ex.estado = "failed"
                ex.fase_actual = f"{ex.fase_actual or ''} (timeout 6h)"
                ex.completado_en = cutoff
                ex.duracion_segundos = round(age, 2)
                count += 1
        db.commit()
        if count:
            logger.info(f"Cleanup: {count} ejecuciones stuck marcadas como failed")
    except Exception:
        logger.exception("Error en limpieza de ejecuciones stuck")
        db.rollback()
    finally:
        db.close()


def _relanzar_fase4(db, eid: int) -> None:
    from celery import chord

    from app.workers.phases.comunes import (
        _marcar_chord_activo,
        _obtener_items_pendientes,
        _reiniciar_items_fallidos,
        al_terminar_items_fase,
        al_terminar_usuarios,
    )
    from app.workers.phases.tarea_item import procesar_item_etl

    _reiniciar_items_fallidos(db, eid, "4")

    pending_users = _obtener_items_pendientes(db, eid, "4", sub_phase="create_user")
    if pending_users:
        task_ids = [procesar_item_etl.si(item.id) for item in pending_users]
        chord(task_ids)(al_terminar_usuarios.s(execution_id=eid))
        _marcar_chord_activo(eid)
        return

    pending_enrols = _obtener_items_pendientes(db, eid, "4", sub_phase="enrol")
    if pending_enrols:
        task_ids = [procesar_item_etl.si(item.id) for item in pending_enrols]
        chord(task_ids)(al_terminar_items_fase.s(execution_id=eid, phase="4"))
        _marcar_chord_activo(eid)
        return

    al_terminar_items_fase.delay([], eid, "4")


@celery_app.task(name="app.workers.cleanup_tasks.recover_stuck_phase")
def recuperar_fase_atascada():
    """Red de seguridad: relanza chords de FASE 3/4 atascados.

    Un chord puede quedar huérfano si un worker cae y su callback nunca se
    ejecuta. Esta tarea (programada por beat cada ~5 min):
    - Resetea items 'processing' viejos a 'pending' (incrementando intentos).
    - Si una fase tiene items pendientes, no tiene un chord activo vigente
      (marcador `chord_active` expirado/ausente) y no hay items procesándose
      recientemente, relanza el chord de la fase.
    """
    from app.db.modelos import ItemOperacion
    from app.repositories.repositorio_operaciones import resolver_items_huerfanos
    from app.workers.phases.comunes import _existen_items_para_ejecucion, _obtener_items_pendientes
    from app.workers.phases.fase3_estructura import al_terminar_items_eliminacion
    from app.workers.utilidades import MINUTOS_TIMEOUT_ITEM_ATASCADO, reiniciar_items_atascados

    db = SessionLocal()
    try:
        now = datetime.now(UTC)

        # Resolver items huérfanos de ejecuciones ya finalizadas antes de
        # procesar las activas: evita que un lote terminado quede "activo"
        # bloqueando subidas (get_active_batch).
        resolver_items_huerfanos(db)

        executions = db.query(Ejecucion).filter(Ejecucion.estado == "running").all()
        for ex in executions:
            eid = ex.id
            checkpoint = ex.checkpoint_fase or {}
            active_ts = checkpoint.get("chord_active")
            chord_alive = False
            if isinstance(active_ts, str):
                try:
                    chord_alive = datetime.fromisoformat(active_ts) > now
                except ValueError:
                    chord_alive = False

            # 1) Siempre resetear items 'processing' viejos: pueden quedar
            #    atascados aunque otros items de la fase sigan activos.
            for phase in ("3", "4"):
                reiniciar_items_atascados(
                    db,
                    batch_id_prefix=f"etl_{phase}_%",
                    execution_id=eid,
                    increment_attempt=True,
                )

            # 2) Relanzar solo si hay pendientes, sin chord vivo y sin
            #    procesamiento reciente en la fase.
            phase_relaunched = False
            for phase in ("3", "4"):
                pending = _obtener_items_pendientes(db, eid, phase)
                if not pending:
                    continue
                recent_processing = (
                    db.query(ItemOperacion)
                    .filter(
                        ItemOperacion.id_lote.like(f"etl_{phase}_%_{eid}"),
                        ItemOperacion.estado == "processing",
                        ItemOperacion.actualizado_en
                        >= now - timedelta(minutes=MINUTOS_TIMEOUT_ITEM_ATASCADO),
                    )
                    .count()
                )
                if recent_processing or chord_alive:
                    continue

                logger.warning(
                    f"Sweeper: fase {phase} de ejecución {eid} con {len(pending)} "
                    f"pendientes sin chord activo ni items recientes, relanzando"
                )
                if phase == "3":
                    al_terminar_items_eliminacion.delay([], eid)
                else:
                    _relanzar_fase4(db, eid)
                phase_relaunched = True
                break

            if not phase_relaunched and not checkpoint.get("phase3_ctx"):
                has_items = _existen_items_para_ejecucion(
                    db, eid, "3"
                ) or _existen_items_para_ejecucion(db, eid, "4")
                if not has_items:
                    heartbeat = ex.progreso_actualizado_en or ex.creado_en
                    stale = heartbeat is not None and (
                        now - heartbeat.replace(tzinfo=UTC)
                        if heartbeat.tzinfo is None
                        else (now - heartbeat)
                    ) >= timedelta(minutes=MINUTOS_TIMEOUT_ITEM_ATASCADO)
                    if stale:
                        retry = checkpoint.get("_retry_count", 0)
                        if retry < 3:
                            import os

                            from sqlalchemy.orm.attributes import flag_modified

                            file_path = os.path.join(settings.UPLOAD_DIR, ex.nombre_archivo)
                            if os.path.isfile(file_path):
                                from app.workers.tareas import procesar_archivo_etl

                                checkpoint["_retry_count"] = retry + 1
                                ex.checkpoint_fase = checkpoint
                                flag_modified(ex, "checkpoint_fase")
                                db.commit()
                                logger.warning(
                                    f"Sweeper: ejecución {eid} atascada en fases 1-2 "
                                    f"(intento {retry + 1}/3), relanzando ETL"
                                )
                                procesar_archivo_etl.delay(ex.id, file_path, ex.semestre)
    except Exception:
        logger.exception("Error en recuperación de fases atascadas")
        db.rollback()
    finally:
        db.close()
