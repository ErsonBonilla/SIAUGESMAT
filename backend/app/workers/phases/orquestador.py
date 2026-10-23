import logging

from celery import chord

from app.celery_app import celery_app
from app.core.config import settings
from app.db.sesion import SessionLocal
from app.integrations.integracion_moodle import IntegracionMoodle
from app.repositories.repositorio_ejecuciones import (
    actualizar_progreso,
    guardar_checkpoint,
    incrementar_metrica,
    marcar_chord_activo,
    marcar_fallido,
    obtener_checkpoint,
    obtener_ejecucion,
)
from app.repositories.repositorio_registros import guardar_error, guardar_log
from app.services.fabrica_moodle import obtener_servicio_moodle
from app.services.mensajes_error import traducir_error
from app.workers.phases.base import ContextoFase
from app.workers.phases.comunes import (
    _lanzar_chord_items,
    _obtener_items_pendientes,
    al_terminar_items_fase,
    al_terminar_usuarios,
)
from app.workers.phases.fase3_estructura import (
    _crear_items_fase3,
    _lanzar_chord_eliminacion,
)
from app.workers.phases.fase4_personas import _crear_items_fase4_sincrono
from app.workers.phases.tarea_item import procesar_item_etl
from app.workers.utilidades import _ejecutar_async

logger = logging.getLogger(__name__)


def _guardar_datos_fase2_en_checkpoint(db, eid, etl_data, metrics, phase2_data, modalidad, mode):
    guardar_checkpoint(
        db,
        eid,
        "phase3_ctx",
        {
            "courses": etl_data.get("courses", []),
            "users": etl_data.get("users", []),
            "existing_courses": phase2_data.get("1", {}).get("courses", []),
            "metrics": metrics,
            "modalidad": modalidad,
            "mode": mode,
            "comparison": phase2_data.get("2", {}).get("comparison", {}),
            "missing_categories": phase2_data.get("2", {}).get("missing_categories", []),
            "categories_to_relocate": phase2_data.get("2", {}).get("categories_to_relocate", []),
            "users_to_create": phase2_data.get("2", {}).get("users_to_create", []),
            "resolved_enrolments": phase2_data.get("2", {}).get("resolved_enrolments", []),
            "username_map": phase2_data.get("1", {}).get("username_map", {}),
        },
    )


@celery_app.task(
    name="app.workers.phases.orchestrator.process_etl_phase",
    bind=True,
    soft_time_limit=3600,
    time_limit=7200,
)
def procesar_fase_etl(self, execution_id: int, phase: str):
    db = SessionLocal()
    try:
        execution = obtener_ejecucion(db, execution_id)
        if not execution:
            logger.error(f"Ejecución {execution_id} no encontrada para FASE {phase}")
            return
        if execution.estado in ("paused", "cancelled"):
            logger.info(f"FASE {phase}: ejecución {execution.estado}, no se lanzan subtareas")
            return

        phase3_ctx = obtener_checkpoint(db, execution_id) or {}
        ctx_data = phase3_ctx.get("phase3_ctx", {})
        comparison = ctx_data.get("comparison", {})
        modalidad = ctx_data.get("modalidad", execution.modalidad or "DISTANCIA")
        mode = ctx_data.get("mode", execution.modo or "both")

        def _procesar_cursos():
            return mode in ("courses", "both")

        def _procesar_usuarios():
            return mode in ("users", "both")

        if phase == "3":
            actualizar_progreso(db, execution_id, 34, "Preparando items de estructura…", paso=3)

            if _procesar_cursos() and ctx_data.get("missing_categories"):

                async def _crear_categorias():
                    ms = obtener_servicio_moodle(modalidad)
                    try:
                        for cat in ctx_data["missing_categories"]:
                            existing = await ms.obtener_categorias(idnumber=cat["idnumber"])
                            if existing:
                                logger.info(f"Categoría {cat['idnumber']} ya existe, omitiendo")
                                continue
                            await ms.crear_categorias([cat])
                            guardar_log(
                                db,
                                execution_id,
                                "3",
                                "category_created",
                                cat["idnumber"],
                                {
                                    "name": cat.get("name", ""),
                                    "parent": cat.get("parent", ""),
                                },
                            )
                            incrementar_metrica(db, execution_id, "categories_created")
                    finally:
                        await ms.cerrar()

                try:
                    _ejecutar_async(_crear_categorias())
                except Exception as e:
                    logger.exception(f"Error creando categorías: {e}")
                    guardar_error(db, execution_id, "3", None, traducir_error(e))

            cats_to_relocate = ctx_data.get("categories_to_relocate", [])
            if _procesar_cursos() and cats_to_relocate:

                async def _reubicar_categorias():
                    ms = obtener_servicio_moodle(modalidad)
                    integ = IntegracionMoodle(ms)
                    try:
                        for cat in cats_to_relocate:
                            ok = await integ.reubicar_categoria(
                                idnumber=cat["idnumber"],
                                moodle_id=cat["moodle_id"],
                                target_parent_idn=cat["expected_parent_idn"],
                            )
                            if ok:
                                logger.info(f"Categoría {cat['idnumber']} reubicada correctamente")
                    finally:
                        await ms.cerrar()

                try:
                    _ejecutar_async(_reubicar_categorias())
                except Exception as e:
                    logger.exception(f"Error reubicando categorías: {e}")
                    guardar_error(db, execution_id, "3", None, traducir_error(e))

            if not comparison:
                logger.info("FASE 3: sin datos de comparación, saltando")
                al_terminar_items_fase.delay([], execution_id, "3")
                return

            actualizar_progreso(
                db, execution_id, 34, "Resolviendo templates y creando items…", paso=3
            )
            item_counts = _crear_items_fase3(db, execution_id, ctx_data, comparison, modalidad)
            total = sum(item_counts.values())
            if total == 0:
                logger.info("FASE 3: sin items que procesar")
                al_terminar_items_fase.delay([], execution_id, "3")
                return

            delete_items = _obtener_items_pendientes(db, execution_id, "3", "delete")
            structure_items = _obtener_items_pendientes(db, execution_id, "3", "structure")

            if delete_items:
                logger.info(
                    f"FASE 3: lanzando {len(delete_items)} delete(s) + {len(structure_items)} estructura(s)"
                )
                _lanzar_chord_eliminacion(execution_id, delete_items)
            elif structure_items:
                _lanzar_chord_items(execution_id, structure_items)
            else:
                al_terminar_items_fase.delay([], execution_id, "3")

        elif phase == "4":
            actualizar_progreso(db, execution_id, 65, "Creando items de personas…", paso=4)
            item_counts = _crear_items_fase4_sincrono(db, execution_id, ctx_data, modalidad)
            total = sum(item_counts.values())
            if total == 0:
                logger.info("FASE 4: sin items que procesar")
                al_terminar_items_fase.delay([], execution_id, "4")
                return

            user_items = _obtener_items_pendientes(db, execution_id, "4", sub_phase="create_user")
            enrol_items = _obtener_items_pendientes(db, execution_id, "4", sub_phase="enrol")

            if user_items:
                logger.info(f"FASE 4: creando {len(user_items)} usuario(s)")
                marcar_chord_activo(db, execution_id)
                task_ids = [procesar_item_etl.si(item.id) for item in user_items]
                chord(task_ids)(
                    al_terminar_usuarios.s(
                        execution_id=execution_id,
                    )
                )
            elif enrol_items:
                logger.info(f"FASE 4: enrolando {len(enrol_items)} profesor(es)")
                marcar_chord_activo(db, execution_id)
                task_ids = [procesar_item_etl.si(item.id) for item in enrol_items]
                chord(task_ids)(al_terminar_items_fase.s(execution_id=execution_id, phase="4"))
            else:
                al_terminar_items_fase.delay([], execution_id, "4")

    except Exception as e:
        logger.exception(f"Error en FASE {phase}: {e}")
        try:
            db.rollback()
            guardar_error(db, execution_id, "critical", None, traducir_error(e))
            marcar_fallido(db, execution_id, 0)
        except Exception:
            logger.exception("Error en rollback/error handling post-fallo de FASE {phase}")
    finally:
        db.close()


def _guardar_checkpoint_fase(db, eid, ctx: ContextoFase, nombre_fase: str):
    if nombre_fase == "1":
        guardar_checkpoint(
            db,
            eid,
            "1",
            {
                "cat_idnumbers": list(ctx.idnumeros_categorias_existentes),
                "courses": ctx.cursos_existentes,
                "username_map": ctx.mapa_usuarios,
                "courses_with_teacher": dict(ctx.cursos_con_docente),
            },
        )
    elif nombre_fase == "2":
        guardar_checkpoint(
            db,
            eid,
            "2",
            {
                "comparison": _serializar_comparacion(ctx.comparacion),
                "missing_categories": ctx.categorias_faltantes,
                "categories_to_relocate": ctx.categorias_a_reubicar,
                "users_to_create": ctx.usuarios_a_crear,
                "resolved_enrolments": ctx.matriculas_resueltas,
                "re_upload": ctx.nueva_subida,
            },
        )


def _restaurar_checkpoint(ctx: ContextoFase, data: dict, nombre_fase: str):
    if nombre_fase == "1":
        ctx.idnumeros_categorias_existentes = set(data.get("cat_idnumbers", []))
        ctx.cursos_existentes = data.get("courses", [])
        ctx.mapa_usuarios = data.get("username_map", {})
        ctx.cursos_con_docente = dict(data.get("courses_with_teacher", {}))
    elif nombre_fase == "2":
        ctx.comparacion = data.get("comparison", {})
        ctx.categorias_faltantes = data.get("missing_categories", [])
        ctx.categorias_a_reubicar = data.get("categories_to_relocate", [])
        ctx.usuarios_a_crear = data.get("users_to_create", [])
        ctx.matriculas_resueltas = data.get("resolved_enrolments", [])
        ctx.nueva_subida = data.get("re_upload", False)


def _restaurar_checkpoint_progreso(ctx: ContextoFase, data: dict, nombre_fase: str):
    ctx.metricas.update(data.get("metrics", {}))
    ctx.mapa_usuarios.update(data.get("username_map", {}))


def _serializar_comparacion(comparison: dict) -> dict:
    result = {}
    for k, v in comparison.items():
        if k == "logs":
            continue
        if isinstance(v, set):
            result[k] = list(v)
        elif isinstance(v, list):
            result[k] = v
        else:
            result[k] = v
    return result


def _es_eliminacion_confirmada(db, execution_id: int) -> bool:
    from app.db.modelos import Ejecucion

    ex = db.query(Ejecucion).filter(Ejecucion.id == execution_id).first()
    if not ex or not ex.checkpoint_fase:
        return False
    return ex.checkpoint_fase.get("delete_confirmed", False)


def _requerir_revision(db, execution_id: int, ctx):
    from sqlalchemy.orm.attributes import flag_modified

    from app.db.modelos import Ejecucion

    ex = db.query(Ejecucion).filter(Ejecucion.id == execution_id).first()
    if ex:
        to_delete_count = len(ctx.comparacion.get("to_delete", []))
        ex.estado = "review_required"
        ex.fase_actual = f"Revisión requerida: {to_delete_count} cursos a eliminar"
        ex.porcentaje_progreso = 30
        ex.metricas = {
            **(ex.metricas or {}),
            "pending_delete_count": to_delete_count,
        }
        if ex.checkpoint_fase is None:
            ex.checkpoint_fase = {}
        ex.checkpoint_fase["delete_review"] = {
            "to_delete_count": to_delete_count,
            "to_create_count": len(ctx.comparacion.get("to_create", [])),
            "threshold": settings.MAX_AUTO_DELETE_COURSES,
        }
        flag_modified(ex, "checkpoint_fase")
        db.commit()


def _incrementar_conteo_reintentos(db, execution_id: int) -> int:
    from sqlalchemy.orm.attributes import flag_modified

    from app.db.modelos import Ejecucion

    ex = db.query(Ejecucion).filter(Ejecucion.id == execution_id).first()
    if not ex:
        return 0
    if ex.checkpoint_fase is None:
        ex.checkpoint_fase = {}
    count = ex.checkpoint_fase.get("_retry_count", 0) + 1
    ex.checkpoint_fase["_retry_count"] = count
    flag_modified(ex, "checkpoint_fase")
    db.commit()
    return count
