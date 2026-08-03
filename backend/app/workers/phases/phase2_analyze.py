import logging
from typing import Dict

from app.pipeline.categories import classify_categories
from app.pipeline.enrolments import resolve_enrolments, users_to_create
from app.pipeline.plan import plan_log_entries
from app.repositories import log_repo
from app.repositories.execution_repo import is_reupload, update_progress
from app.services.course_comparison import CourseComparisonService
from app.services.error_messages import translate_error
from app.workers.phases.base import BasePhase, PhaseContext

logger = logging.getLogger(__name__)


def persist_plan_logs(db, execution_id: int, comparison: Dict, fullname_map: Dict = None) -> int:
    """Persiste el plan de acciones de la comparación a ExecutionLog.

    Los logs de comparación se guardan con prefijo ``planned_`` para
    distinguirlos de las acciones realmente ejecutadas (que escribe
    ``_log_success`` en fases posteriores) y evitar colisiones en los
    reportes existentes. Las alertas se persisten con su acción propia.

    Returns:
        Número de registros persistidos.
    """
    count = 0
    for action, identifier, detail in plan_log_entries(comparison, fullname_map):
        log_repo.save_log(db, execution_id, "2", action, identifier, detail)
        count += 1
    db.commit()
    return count


class AnalyzePhase(BasePhase):
    phase_name = "2"

    async def run(self, ctx: PhaseContext) -> None:
        db = ctx.db
        eid = ctx.execution_id
        mode = ctx.mode
        etl_data = ctx.etl_data

        update_progress(db, eid, 16, "Analizando datos…", step=2)

        try:
            resolved_enrolments = resolve_enrolments(
                etl_data["enrolments"], ctx.username_map,
            )
            ctx.resolved_enrolments = resolved_enrolments

            ctx.missing_categories, ctx.categories_to_relocate = classify_categories(
                etl_data["categories"],
                ctx.existing_cat_idnumbers,
                ctx.all_categories_map,
            )

            if ctx.missing_categories:
                log_repo.save_log(db, eid, "2", "categories_missing", detail={
                    "count": len(ctx.missing_categories),
                    "categories": [c["idnumber"] for c in ctx.missing_categories],
                })
            if ctx.categories_to_relocate:
                log_repo.save_log(db, eid, "2", "categories_to_relocate", detail={
                    "count": len(ctx.categories_to_relocate),
                    "categories": [c["idnumber"] for c in ctx.categories_to_relocate],
                })

            ctx.re_upload = is_reupload(
                db, ctx.execution.semester,
                ctx.execution.modalidad or "", eid,
            )

            ctx.comparison = await CourseComparisonService.compare(
                ctx.existing_courses,
                etl_data["courses"],
                resolved_enrolments,
                re_upload=ctx.re_upload,
                courses_with_teacher=ctx.courses_with_teacher,
            )

            persist_plan_logs(db, eid, ctx.comparison, {
                c.get("shortname", ""): c.get("fullname", "") for c in ctx.existing_courses
            })

            if mode in ("users", "both"):
                ctx.users_to_create = users_to_create(etl_data["users"], ctx.username_map)

            ctx.metrics["alerts"] = len(ctx.comparison.get("alerts", []))

            log_repo.save_log(db, eid, "2", "phase2_complete", detail={
                "categories_to_create": len(ctx.missing_categories),
                "courses_to_create": len(ctx.comparison.get("to_create", [])),
                "courses_to_delete": len(ctx.comparison.get("to_delete", [])),
                "courses_to_activate": len(ctx.comparison.get("to_activate", [])),
                "courses_to_hide": len(ctx.comparison.get("to_hide", [])),
                "courses_to_update": len(ctx.comparison.get("to_update", [])),
                "users_to_create": len(ctx.users_to_create),
                "alerts": ctx.metrics["alerts"],
            })
            logger.info(
                f"FASE 2: crear {len(ctx.missing_categories)} cats, "
                f"reubicar {len(ctx.categories_to_relocate)} cats, "
                f"{len(ctx.comparison.get('to_create', []))} cursos, "
                f"eliminar {len(ctx.comparison.get('to_delete', []))}, "
                f"{len(ctx.users_to_create)} usuarios"
            )
            update_progress(db, eid, 24, "Plan de acciones definido")

        except Exception as e:
            logger.exception(f"Error en FASE 2 (análisis): {e}")
            log_repo.save_error(db, eid, "2", "", translate_error(e))
            ctx.metrics["total_errors"] += 1
            raise
