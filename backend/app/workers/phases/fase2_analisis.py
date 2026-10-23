import logging

from app.core.config import settings
from app.pipeline.categorias import clasificar_categorias
from app.pipeline.comparacion_cursos import ServicioComparacionCursos
from app.pipeline.matriculaciones import resolver_matriculaciones, usuarios_a_crear
from app.pipeline.plan import entradas_log_plan
from app.repositories import repositorio_registros
from app.repositories.repositorio_ejecuciones import actualizar_progreso, es_re_subida
from app.services.mensajes_error import traducir_error
from app.workers.phases.base import ContextoFase, FaseBase

logger = logging.getLogger(__name__)


def persistir_logs_plan(db, execution_id: int, comparison: dict, fullname_map: dict = None) -> int:
    """Persiste el plan de acciones de la comparación a ExecutionLog.

    Los logs de comparación se guardan con prefijo ``planned_`` para
    distinguirlos de las acciones realmente ejecutadas (que escribe
    ``_log_success`` en fases posteriores) y evitar colisiones en los
    reportes existentes. Las alertas se persisten con su acción propia.

    Returns:
        Número de registros persistidos.
    """
    count = 0
    for action, identifier, detail in entradas_log_plan(comparison, fullname_map):
        repositorio_registros.guardar_log(db, execution_id, "2", action, identifier, detail)
        count += 1
    db.commit()
    return count


class FaseAnalisis(FaseBase):
    nombre_fase = "2"

    async def ejecutar(self, ctx: ContextoFase) -> None:
        db = ctx.db
        eid = ctx.ejecucion_id
        mode = ctx.modo
        etl_data = ctx.datos_etl

        actualizar_progreso(db, eid, 16, "Analizando datos…", paso=2)

        try:
            resolved_enrolments = resolver_matriculaciones(
                etl_data["enrolments"],
                ctx.mapa_usuarios,
            )
            ctx.matriculas_resueltas = resolved_enrolments

            ctx.categorias_faltantes, ctx.categorias_a_reubicar = clasificar_categorias(
                etl_data["categories"],
                ctx.idnumeros_categorias_existentes,
                ctx.mapa_todas_categorias,
            )

            if ctx.categorias_faltantes:
                repositorio_registros.guardar_log(
                    db,
                    eid,
                    "2",
                    "categories_missing",
                    detalle={
                        "count": len(ctx.categorias_faltantes),
                        "categories": [c["idnumber"] for c in ctx.categorias_faltantes],
                    },
                )
            if ctx.categorias_a_reubicar:
                repositorio_registros.guardar_log(
                    db,
                    eid,
                    "2",
                    "categories_to_relocate",
                    detalle={
                        "count": len(ctx.categorias_a_reubicar),
                        "categories": [c["idnumber"] for c in ctx.categorias_a_reubicar],
                    },
                )

            ctx.nueva_subida = es_re_subida(
                db,
                ctx.ejecucion.semestre,
                ctx.ejecucion.modalidad or "",
                eid,
            )

            ctx.comparacion = await ServicioComparacionCursos.comparar(
                ctx.cursos_existentes,
                etl_data["courses"],
                resolved_enrolments,
                re_upload=ctx.nueva_subida,
                courses_with_teacher=ctx.cursos_con_docente,
                username_emails=ctx.correos_usuarios,
                max_age_seconds=settings.COURSE_MAX_AGE_SECONDS,
                disappeared_age_seconds=settings.COURSE_DISAPPEARED_AGE_SECONDS,
            )

            persistir_logs_plan(
                db,
                eid,
                ctx.comparacion,
                {c.get("shortname", ""): c.get("fullname", "") for c in ctx.cursos_existentes},
            )

            if mode in ("users", "both"):
                ctx.usuarios_a_crear = usuarios_a_crear(etl_data["users"], ctx.mapa_usuarios)

            ctx.metricas["alerts"] = len(ctx.comparacion.get("alerts", []))

            repositorio_registros.guardar_log(
                db,
                eid,
                "2",
                "phase2_complete",
                detalle={
                    "categories_to_create": len(ctx.categorias_faltantes),
                    "courses_to_create": len(ctx.comparacion.get("to_create", [])),
                    "courses_to_delete": len(ctx.comparacion.get("to_delete", [])),
                    "courses_to_activate": len(ctx.comparacion.get("to_activate", [])),
                    "courses_to_hide": len(ctx.comparacion.get("to_hide", [])),
                    "courses_to_update": len(ctx.comparacion.get("to_update", [])),
                    "users_to_create": len(ctx.usuarios_a_crear),
                    "alerts": ctx.metricas["alerts"],
                },
            )
            logger.info(
                f"FASE 2: crear {len(ctx.categorias_faltantes)} cats, "
                f"reubicar {len(ctx.categorias_a_reubicar)} cats, "
                f"{len(ctx.comparacion.get('to_create', []))} cursos, "
                f"eliminar {len(ctx.comparacion.get('to_delete', []))}, "
                f"{len(ctx.usuarios_a_crear)} usuarios"
            )
            actualizar_progreso(db, eid, 24, "Plan de acciones definido")

        except Exception as e:
            logger.exception(f"Error en FASE 2 (análisis): {e}")
            repositorio_registros.guardar_error(db, eid, "2", "", traducir_error(e))
            ctx.metricas["total_errors"] += 1
            raise
