import hashlib
import logging
from datetime import UTC, datetime

from celery import chord
from sqlalchemy import func
from sqlalchemy import text as sql_text

from app.celery_app import celery_app
from app.db.modelos import ItemOperacion
from app.db.sesion import SessionLocal
from app.repositories.repositorio_ejecuciones import (
    actualizar_progreso,
    establecer_directorio_reportes,
    guardar_checkpoint,
    limpiar_checkpoint,
    limpiar_chord_activo,
    marcar_chord_activo,
    marcar_completado,
    marcar_fallido,
    obtener_ejecucion,
)
from app.repositories.repositorio_registros import guardar_error
from app.services.mensajes_error import traducir_error
from app.services.reportes import ServicioReportes
from app.workers.phases.base import ErrorMoodleSobrecargado
from app.workers.phases.tarea_item import procesar_item_etl
from app.workers.utilidades import reiniciar_items_atascados

logger = logging.getLogger(__name__)


def _adquirir_bloqueo_asesor(db, execution_id: int, phase: str) -> bool:
    if db.get_bind().dialect.name != "postgresql":
        return True
    key = f"etl_lock_{execution_id}_{phase}".encode()
    lock_id = int(hashlib.sha256(key).hexdigest(), 16) % (2**63)
    result = db.execute(
        sql_text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
        {"lock_id": lock_id},
    ).scalar()
    return bool(result)


def _existen_items_para_ejecucion(db, execution_id, phase):
    return (
        db.query(ItemOperacion)
        .filter(ItemOperacion.id_lote.like(f"etl_{phase}_%_{execution_id}"))
        .first()
        is not None
    )


def _obtener_conteos_pendientes(db, execution_id: int, phase: str) -> dict[str, int]:
    items = (
        db.query(ItemOperacion)
        .filter(
            ItemOperacion.id_lote.like(f"etl_{phase}_%_{execution_id}"),
            ItemOperacion.estado == "pending",
        )
        .all()
    )
    counts: dict[str, int] = {}
    for item in items:
        action = (item.detalle or {}).get("action", "unknown")
        counts[action] = counts.get(action, 0) + 1
    return counts


def _obtener_items_pendientes(db, execution_id, phase, sub_phase=None):
    query = db.query(ItemOperacion).filter(
        ItemOperacion.id_lote.like(f"etl_{phase}_%_{execution_id}"),
        ItemOperacion.estado == "pending",
    )
    if sub_phase:
        if sub_phase == "structure":
            query = query.filter(sql_text("detalle->>'action' != 'delete'"))
        else:
            query = query.filter(sql_text("detalle->>'action' = :action")).params(action=sub_phase)
    return query.all()


RETRY_MAX_ATTEMPTS = 3


def _reiniciar_items_fallidos(db, execution_id, phase):
    """Devuelve a 'pending' los items 'failed' con intentos restantes.

    Permite reintentar errores transitorios (p. ej. 500 de Moodle) hasta
    ``RETRY_MAX_ATTEMPTS``; los que superen el tope quedan como 'failed'.
    """
    from app.db.modelos import ItemOperacion

    failed = (
        db.query(ItemOperacion)
        .filter(
            ItemOperacion.id_lote.like(f"etl_{phase}_%_{execution_id}"),
            ItemOperacion.estado == "failed",
            ItemOperacion.intento < RETRY_MAX_ATTEMPTS,
        )
        .all()
    )
    if not failed:
        return
    for item in failed:
        item.estado = "pending"
        item.mensaje_error = None
    db.commit()
    logger.warning(f"FASE {phase}: {len(failed)} items failed reintentables reseteados a pending")


def _sincronizar_conteos_lote(db, execution_id):
    """Recomputa completed/failed de los lotes ETL de la ejecución.

    El flujo ETL nunca usó ``update_batch_counts``; los contadores de
    ``operation_batches`` quedaban en 0, rompiendo listados y analítica.
    """
    from app.db.modelos import ItemOperacion, LoteOperacion

    rows = (
        db.query(ItemOperacion.id_lote, ItemOperacion.estado, func.count(ItemOperacion.id))
        .filter(ItemOperacion.id_lote.like(f"etl_%_{execution_id}"))
        .group_by(ItemOperacion.id_lote, ItemOperacion.estado)
        .all()
    )
    totals: dict[str, dict[str, int]] = {}
    for batch_id, status, count in rows:
        bucket = totals.setdefault(batch_id, {"completed": 0, "failed": 0})
        if status == "completed":
            bucket["completed"] += count
        elif status == "failed":
            bucket["failed"] += count

    if not totals:
        return
    for batch_id, counts in totals.items():
        batch = db.query(LoteOperacion).filter(LoteOperacion.id_lote == batch_id).first()
        if batch:
            batch.completados = counts["completed"]
            batch.fallidos = counts["failed"]
    db.commit()


def _marcar_chord_activo(execution_id):
    """Marca el chord recién lanzado como activo (para el sweeper)."""
    db = SessionLocal()
    try:
        marcar_chord_activo(db, execution_id)
    except Exception:
        logger.exception(f"No se pudo marcar chord activo para ejecución {execution_id}")
    finally:
        db.close()


def _lanzar_chord_items(execution_id, structure_items):
    if not structure_items:
        al_terminar_items_fase.delay([], execution_id, "3")
        return
    task_ids = [procesar_item_etl.si(item.id) for item in structure_items]
    _marcar_chord_activo(execution_id)
    chord(task_ids)(al_terminar_items_fase.s(execution_id=execution_id, phase="3"))


@celery_app.task(
    name="app.workers.phases.common.on_phase_items_done",
    bind=True,
    autoretry_for=(ErrorMoodleSobrecargado,),
    max_retries=3,
    default_retry_delay=10,
    retry_backoff=True,
    retry_backoff_max=60,
)
def al_terminar_items_fase(self, results, execution_id, phase):
    _cb_entered = datetime.now(UTC)
    db = SessionLocal()
    execution = None
    try:
        execution = obtener_ejecucion(db, execution_id)
        if not execution or execution.estado in ("paused", "cancelled"):
            return

        limpiar_chord_activo(db, execution_id)

        stuck = reiniciar_items_atascados(
            db,
            batch_id_prefix=f"etl_{phase}_%",
            execution_id=execution_id,
            increment_attempt=True,
        )
        if stuck:
            logger.warning(f"FASE {phase}: {len(stuck)} items stuck reseteados a pending")

        if phase == "3":
            _reiniciar_items_fallidos(db, execution_id, "3")
            pending = _obtener_items_pendientes(db, execution_id, "3")
            if pending:
                logger.warning(f"FASE 3: {len(pending)} items pendientes tras chord, relanzando")
                _lanzar_chord_items(execution_id, pending)
                return
        elif phase == "4":
            _reiniciar_items_fallidos(db, execution_id, "4")
            pending = _obtener_items_pendientes(db, execution_id, "4")
            if pending:
                logger.warning(f"FASE 4: {len(pending)} items pendientes tras chord, relanzando")
                task_ids = [procesar_item_etl.si(item.id) for item in pending]
                _marcar_chord_activo(execution_id)
                chord(task_ids)(al_terminar_items_fase.s(execution_id=execution_id, phase="4"))
                return

        _sincronizar_metricas_desde_items(db, execution_id)
        _sincronizar_conteos_lote(db, execution_id)

        if phase == "3":
            guardar_checkpoint(
                db, execution_id, "3", {"completed": True, "at": datetime.now(UTC).isoformat()}
            )
            actualizar_progreso(db, execution_id, 62, "FASE 3 completada, lanzando FASE 4", paso=3)
            logger.info(f"FASE 3 completada para ejecución {execution_id}")
            celery_app.send_task(
                "app.workers.phases.orchestrator.process_etl_phase", args=[execution_id, "4"]
            )

        elif phase == "4":
            guardar_checkpoint(
                db, execution_id, "4", {"completed": True, "at": datetime.now(UTC).isoformat()}
            )
            actualizar_progreso(db, execution_id, 85, "Generando reportes…", paso=5)
            report_ok = True
            try:
                report_dir = ServicioReportes.generar_todos(execution_id, db)
                establecer_directorio_reportes(db, execution_id, report_dir)
                logger.info(f"Reportes generados en: {report_dir}")
            except Exception as e:
                logger.exception(f"Error generando reportes: {e}")
                guardar_error(db, execution_id, "critical", None, traducir_error(e))
                report_ok = False

            actualizar_progreso(db, execution_id, 95, "Finalizando…")
            _cb_done = datetime.now(UTC)
            metrics = execution.metricas or {}
            iniciado_dt = execution.iniciado_en
            if iniciado_dt and iniciado_dt.tzinfo is None:
                iniciado_dt = iniciado_dt.replace(tzinfo=UTC)
            marcar_completado(
                db,
                execution_id,
                metrics,
                conteo_errores=metrics.get("total_errors", 0),
                duracion_segundos=(iniciado_dt and (_cb_done - iniciado_dt).total_seconds()) or 0,
            )
            limpiar_checkpoint(db, execution_id)
            actualizar_progreso(db, execution_id, 100, "Ejecución completada")
            logger.info(
                f"Ejecución {execution_id} completada {'' if report_ok else '(sin reportes)'}"
            )

    except Exception as e:
        logger.exception(f"Error en on_phase_items_done (fase {phase}): {e}")
        try:
            db.rollback()
            guardar_error(db, execution_id, "critical", None, traducir_error(e))
            marcar_fallido(
                db,
                execution_id,
                (datetime.now(UTC) - _cb_entered).total_seconds()
                if execution and execution.iniciado_en
                else 0,
            )
        except Exception:
            logger.exception(f"Error marcando fallido on_phase_items_done (fase {phase})")
    finally:
        db.close()


@celery_app.task(name="app.workers.phases.common.on_users_done", bind=True)
def al_terminar_usuarios(self, results, execution_id):
    db = SessionLocal()
    try:
        execution = obtener_ejecucion(db, execution_id)
        if execution and execution.estado not in ("paused", "cancelled"):
            limpiar_chord_activo(db, execution_id)

        failed_users = (
            db.query(ItemOperacion)
            .filter(
                ItemOperacion.id_lote.like(f"etl_4_%_{execution_id}"),
                sql_text("detalle->>'action' = 'create_user'"),
                ItemOperacion.estado == "failed",
            )
            .all()
        )
        if failed_users:
            failed_usernames = {item.identificador for item in failed_users}
            logger.warning(
                f"on_users_done: {len(failed_usernames)} usuario(s) no creados, "
                f"marcando enrolments correspondientes como fallidos"
            )
            enrol_to_fail = (
                db.query(ItemOperacion)
                .filter(
                    ItemOperacion.id_lote.like(f"etl_4_%_{execution_id}"),
                    sql_text("detalle->>'action' = 'enrol'"),
                    ItemOperacion.estado == "pending",
                    ItemOperacion.identificador.in_(failed_usernames),
                )
                .all()
            )
            for item in enrol_to_fail:
                item.estado = "failed"
                item.mensaje_error = "Usuario no pudo crearse en Moodle"
            if enrol_to_fail:
                db.commit()
                logger.info(
                    f"Marcados {len(enrol_to_fail)} enrolments como failed por usuario no creado"
                )

        enrol_items = _obtener_items_pendientes(db, execution_id, "4", sub_phase="enrol")
        if enrol_items:
            logger.info(f"on_users_done: enrolando {len(enrol_items)} profesor(es)")
            task_ids = [procesar_item_etl.si(item.id) for item in enrol_items]
            _marcar_chord_activo(execution_id)
            chord(task_ids)(al_terminar_items_fase.s(execution_id=execution_id, phase="4"))
        else:
            logger.info("on_users_done: sin enrolamientos pendientes")
            al_terminar_items_fase.delay([], execution_id, "4")
    except Exception as e:
        logger.exception(f"Error en on_users_done: {e}")
        al_terminar_items_fase.delay([], execution_id, "4")
    finally:
        db.close()


def _sincronizar_metricas_desde_items(db, execution_id):
    from app.db.modelos import ItemOperacion

    items = (
        db.query(ItemOperacion).filter(ItemOperacion.id_lote.like(f"etl_%_{execution_id}")).all()
    )

    metrics = {
        "courses_deleted": 0,
        "courses_activated": 0,
        "courses_hidden": 0,
        "courses_renamed": 0,
        "courses_created": 0,
        "users_created": 0,
        "enrolments": 0,
        "enrolment_errors": 0,
        "total_errors": 0,
    }

    for item in items:
        action = (item.detalle or {}).get("action", "")
        if item.estado == "completed":
            key = {
                "delete": "courses_deleted",
                "activate": "courses_activated",
                "hide": "courses_hidden",
                "rename": "courses_renamed",
                "create": "courses_created",
                "create_user": "users_created",
                "enrol": "enrolments",
            }.get(action)
            if key:
                metrics[key] = metrics.get(key, 0) + 1
        elif item.estado == "failed":
            if action == "enrol":
                metrics["enrolment_errors"] = metrics.get("enrolment_errors", 0) + 1
            metrics["total_errors"] = metrics.get("total_errors", 0) + 1

    ex = obtener_ejecucion(db, execution_id)
    if ex:
        from app.db.modelos import RegistroError

        errores_db = (
            db.query(func.count(RegistroError.id))
            .filter(RegistroError.ejecucion_id == execution_id)
            .scalar()
            or 0
        )
        existing = ex.metricas or {}
        errores_previos = int(existing.get("total_errors") or 0)
        for key in metrics:
            existing[key] = metrics[key]
        existing["total_errors"] = max(metrics["total_errors"], errores_previos, errores_db)
        existing["total_operations"] = sum(
            metrics.get(k, 0)
            for k in (
                "courses_created",
                "courses_deleted",
                "courses_activated",
                "courses_hidden",
                "courses_renamed",
                "users_created",
                "enrolments",
            )
        )
        existing["alerts"] = existing.get("alerts", 0)
        ex.metricas = existing
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(ex, "metricas")
        db.commit()
