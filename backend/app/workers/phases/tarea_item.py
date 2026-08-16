import logging
from datetime import UTC, datetime

from celery.signals import worker_process_init
from sqlalchemy import func

from app.celery_app import celery_app
from app.core.configuracion_logging import FiltroContextoEjecucion
from app.db.sesion import SessionLocal
from app.integrations.integracion_moodle import IntegracionMoodle
from app.repositories.repositorio_ejecuciones import (
    debe_cancelarse,
    incrementar_metrica,
    sincronizar_conteo_errores,
)
from app.repositories.repositorio_operaciones import (
    actualizar_item,
    obtener_item,
    reclamar_item,
    resolver_items_huerfanos,
)
from app.repositories.repositorio_registros import guardar_error, guardar_log
from app.services.errores_moodle import ErrorMoodleSobrecargado, es_moodle_sobrecargado
from app.services.fabrica_moodle import obtener_servicio_moodle
from app.services.mensajes_error import traducir_error
from app.workers.utilidades import ejecutar_moodle_async, reiniciar_items_atascados

logger = logging.getLogger(__name__)


def _reset_stuck_items():
    try:
        db = SessionLocal()
        # Primero resolver items huérfanos de ejecuciones ya finalizadas: si
        # no, el reset global de abajo los devolvería a "pending" y nadie los
        # reclamaría (el chord/sweeper solo operan sobre ejecuciones activas),
        # dejando su lote "activo" y bloqueando subidas.
        resolver_items_huerfanos(db)
        reiniciar_items_atascados(db)
    except Exception:
        logger.exception("Error reseteando items stuck en etl_item_task")
    finally:
        db.close()


@worker_process_init.connect
def _reset_stuck_items_al_iniciar_worker(**kwargs):
    _reset_stuck_items()


@celery_app.task(
    name="app.workers.phases.item_task.process_etl_item",
    bind=True,
    autoretry_for=(ErrorMoodleSobrecargado,),
    max_retries=10,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    soft_time_limit=900,
    time_limit=1800,
)
def procesar_item_etl(self, item_id: int):
    db = SessionLocal()
    try:
        item = obtener_item(db, item_id)
        if not item:
            logger.error(f"Item {item_id} no encontrado")
            return
        if item.estado == "completed":
            return

        detail = item.detalle or {}
        action = detail.get("action")
        execution_id = detail.get("execution_id")
        modalidad = detail.get("modalidad", "DISTANCIA")
        identifier = item.identificador

        FiltroContextoEjecucion.establecer_contexto(
            execution_id=execution_id,
            item_id=item_id,
            action=action,
        )

        if not action:
            actualizar_item(db, item.id, "failed", "Falta 'action' en detail")
            return

        if execution_id and debe_cancelarse(db, execution_id):
            actualizar_item(db, item.id, "failed", "Ejecución cancelada")
            db.commit()
            return

        moodle = obtener_servicio_moodle(modalidad)
        integration = IntegracionMoodle(moodle)

        if not reclamar_item(db, item.id):
            return

        async def _ejecutar():
            success = False
            if action == "delete":
                success = await integration.eliminar_curso(identifier)
            elif action == "activate":
                success = await integration.activar_curso(identifier)
            elif action == "hide":
                success = await integration.ocultar_curso(identifier)
            elif action == "rename":
                success = await integration.renombrar_curso(
                    old_shortname=detail.get("old_shortname", identifier),
                    new_shortname=identifier,
                    new_fullname=detail.get("fullname", ""),
                )
            elif action == "create":
                success = await integration.crear_curso(
                    shortname=identifier,
                    fullname=detail.get("fullname", ""),
                    category_idnumber=detail.get("category_idnumber", ""),
                    template_id=detail.get("template_id"),
                    recreate=detail.get("recreate", False),
                )
            elif action == "create_user":
                username, created = await integration.crear_usuario_si_no_existe(
                    {
                        "username": identifier,
                        "firstname": detail.get("firstname", ""),
                        "lastname": detail.get("lastname", ""),
                        "email": detail.get("email", ""),
                        "password": detail.get("password", ""),
                        "cedula": detail.get("cedula", ""),
                        "city": detail.get("city", ""),
                        "description": detail.get("description", ""),
                    }
                )
                success = username is not None
                if success and username != identifier and execution_id:
                    # El usuario ya existía en Moodle bajo otro username. Se
                    # propaga a los enrolments pendientes para que matrícula
                    # con el username real en lugar del username ETL.
                    from sqlalchemy import text as sql_text

                    from app.db.modelos import ItemOperacion

                    logger.warning(
                        f"create_user: '{identifier}' existe en Moodle como '{username}', "
                        f"actualizando enrolments pendientes"
                    )
                    db.query(ItemOperacion).filter(
                        ItemOperacion.id_lote.like(f"etl_4_%_{execution_id}"),
                        sql_text("detalle->>'action' = 'enrol'"),
                        ItemOperacion.estado == "pending",
                        ItemOperacion.identificador == identifier,
                    ).update({"identificador": username}, synchronize_session=False)
                    db.commit()
                    if not created:
                        guardar_log(
                            db,
                            execution_id,
                            "4",
                            "user_reused_by_email",
                            username,
                            {
                                "etl_username": identifier,
                                "email": detail.get("email", ""),
                                "moodle_username": username,
                                "enrolments_propagated": True,
                            },
                        )
                if success and created and execution_id:
                    guardar_log(
                        db,
                        execution_id,
                        "4",
                        "user_created_createpassword",
                        username,
                        {**detail, "auth": "manual", "base_db": "Manual"},
                    )
            elif action == "enrol":
                course_id = detail.get("_course_id")
                course_map = {detail.get("course_shortname", ""): course_id} if course_id else None
                result = await integration.matricular_docente(
                    username=identifier,
                    course_shortname=detail.get("course_shortname", ""),
                    course_map=course_map,
                    email=detail.get("email", ""),
                )
                success = result["success"]
            else:
                actualizar_item(db, item.id, "failed", f"Acción desconocida: {action}")
                db.commit()
                return

            if success:
                actualizar_item(db, item.id, "completed")
                _log_success(db, execution_id, action, identifier, detail)
            else:
                error = integration.ultimo_error or f"Error desconocido ({action}:{identifier})"
                if action == "enrol":
                    _log_enrol_failure(db, execution_id, identifier, detail, error)
                actualizar_item(db, item.id, "failed", error)
                _manejar_error(execution_id, action, identifier, error, db=db)
            db.commit()

        try:
            ejecutar_moodle_async(moodle, _ejecutar())
        except ErrorMoodleSobrecargado:
            db.commit()
            raise
        except Exception as e:
            if es_moodle_sobrecargado(e):
                db.commit()
                raise ErrorMoodleSobrecargado(str(e)[:200]) from e
            actualizar_item(db, item.id, "failed", traducir_error(e))
            _manejar_error(execution_id, action, identifier, traducir_error(e), db=db)
            db.commit()

        if execution_id:
            _refrescar_progreso_fase(execution_id, db=db)

    except ErrorMoodleSobrecargado:
        if self.request.retries >= self.max_retries:
            error_msg = "Agotados reintentos por sobrecarga de Moodle"
            try:
                actualizar_item(db, item.id, "failed", error_msg)
                if execution_id:
                    _manejar_error(execution_id, action, identifier, error_msg, db=db)
                db.commit()
                logger.exception(
                    f"Item {item_id} marcado failed tras agotar reintentos por sobrecarga"
                )
            except Exception as exc:
                logger.exception(f"Error marcando failed item {item_id} tras sobrecarga: {exc}")
        else:
            raise
    except Exception as e:
        logger.exception(f"Error crítico en item {item_id}: {e}")
        try:
            db.rollback()
            if execution_id and item:
                actualizar_item(db, item.id, "failed", traducir_error(e))
                _manejar_error(execution_id, action, identifier, traducir_error(e), db=db)
                db.commit()
        except Exception as e:
            logger.exception(f"Error actualizando progreso para ejecución {execution_id}: {e}")
    finally:
        FiltroContextoEjecucion.limpiar_contexto()
        db.close()


PROGRESS_REFRESH_SECONDS = 5


def _refrescar_progreso_fase(execution_id, db):
    from app.db.modelos import Ejecucion, ItemOperacion
    from app.pipeline.progreso import calcular_progreso_fase

    try:
        ex = db.query(Ejecucion).filter(Ejecucion.id == execution_id).first()
        if not ex:
            return
        now = datetime.now(UTC)
        if ex.progreso_actualizado_en:
            last_update = ex.progreso_actualizado_en
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=UTC)
            if (now - last_update).total_seconds() < PROGRESS_REFRESH_SECONDS:
                return

        phase3_total = (
            db.query(func.count(ItemOperacion.id))
            .filter(ItemOperacion.id_lote.like(f"etl_3_%_{execution_id}"))
            .scalar()
            or 0
        )
        phase3_done = (
            db.query(func.count(ItemOperacion.id))
            .filter(
                ItemOperacion.id_lote.like(f"etl_3_%_{execution_id}"),
                ItemOperacion.estado.in_(["completed", "failed"]),
            )
            .scalar()
            or 0
        )

        phase4_total = (
            db.query(func.count(ItemOperacion.id))
            .filter(ItemOperacion.id_lote.like(f"etl_4_%_{execution_id}"))
            .scalar()
            or 0
        )
        phase4_done = (
            db.query(func.count(ItemOperacion.id))
            .filter(
                ItemOperacion.id_lote.like(f"etl_4_%_{execution_id}"),
                ItemOperacion.estado.in_(["completed", "failed"]),
            )
            .scalar()
            or 0
        )

        pct = calcular_progreso_fase(
            phase3_total,
            phase3_done,
            phase4_total,
            phase4_done,
        )
        if ex.porcentaje_progreso is None or pct > ex.porcentaje_progreso:
            ex.porcentaje_progreso = pct
            ex.progreso_actualizado_en = now
            db.commit()
    except Exception as e:
        logger.exception(f"Error actualizando progreso para ejecución {execution_id}: {e}")
        # Nota: No cerramos db porque la sesión pertenece al caller


def _log_success(db, execution_id, action, identifier, detail):
    if not execution_id:
        return
    phase = "3" if action in ("delete", "activate", "hide", "rename", "create") else "4"
    log_action = {
        "delete": "course_deleted",
        "activate": "course_activated",
        "hide": "course_hidden",
        "rename": "course_renamed",
        "create": "course_created",
        "create_user": "user_created",
        "enrol": "enrolment_ok",
    }.get(action, action)
    log_detail = {}
    if action == "rename":
        log_detail = {
            "old_shortname": detail.get("old_shortname", ""),
            "old_fullname": detail.get("old_fullname", ""),
            "new_fullname": detail.get("fullname", ""),
        }
    elif action == "enrol":
        log_detail = {
            "course": detail.get("course_shortname", ""),
            "fullname": detail.get("fullname", ""),
            "firstname": detail.get("firstname", ""),
            "lastname": detail.get("lastname", ""),
        }
    elif action in ("delete", "activate", "hide", "create"):
        for key in (
            "reason",
            "old_shortname",
            "old_professor",
            "professor",
            "template_shortname",
            "age_seconds",
            "recreate",
            "fullname",
            "category_idnumber",
            "firstname",
            "lastname",
        ):
            if key in detail:
                log_detail[key] = detail.get(key)
    if log_action != "user_created":
        guardar_log(db, execution_id, phase, log_action, identifier, log_detail)


def _manejar_error(execution_id, action, identifier, error_msg, db):
    if not execution_id:
        return
    try:
        phase = "3" if action in ("delete", "activate", "hide", "rename", "create") else "4"
        guardar_error(db, execution_id, phase, identifier, error_msg)
        metric_key = "enrolment_errors" if action == "enrol" else "total_errors"
        incrementar_metrica(db, execution_id, metric_key)
        if metric_key != "total_errors":
            incrementar_metrica(db, execution_id, "total_errors")
        sincronizar_conteo_errores(db, execution_id)
    except Exception:
        logger.exception(f"Error manejando fallo ETL para {identifier}")
        # Nota: No cerramos db porque la sesión pertenece al caller


def _normalizar_motivo_matriculacion(error_msg: str) -> str:
    """Normaliza el motivo de un fallo de matriculación para el reporte.

    Los reportes inc_usuarios_inactivos y audit_matriculas esperan reasons
    como ``user_not_found``/``user_inactive``, pero los fallos llegan como
    mensajes en español o warningcodes de la API de Moodle.
    """
    m = (error_msg or "").lower()
    if "usuario no encontrado" in m or "user not found" in m:
        return "user_not_found"
    if "curso no encontrado" in m or "course not found" in m:
        return "course_not_found"
    if "inactive" in m or "suspendid" in m or "no activo" in m or "usernotactive" in m:
        return "user_inactive"
    if "alreadyenrolled" in m or "ya matriculado" in m:
        return "already_enrolled"
    return (error_msg or "").strip() or "unknown"


def _log_enrol_failure(db, execution_id, identifier, detail, error_msg):
    if not execution_id:
        return
    guardar_log(
        db,
        execution_id,
        "4",
        "enrolment_failed",
        identifier,
        {
            "course": detail.get("course_shortname", ""),
            "fullname": detail.get("fullname", ""),
            "reason": _normalizar_motivo_matriculacion(error_msg),
        },
    )
