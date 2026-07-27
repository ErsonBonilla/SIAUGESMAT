import logging
from typing import Dict, List

from app.repositories import log_repo
from app.repositories.execution_repo import is_reupload, update_progress
from app.services.course_comparison import CourseComparisonService
from app.services.error_messages import translate_error
from app.workers.phases.base import BasePhase, PhaseContext

logger = logging.getLogger(__name__)


class AnalyzePhase(BasePhase):
    phase_name = "2"

    async def run(self, ctx: PhaseContext) -> None:
        db = ctx.db
        eid = ctx.execution_id
        mode = ctx.mode
        etl_data = ctx.etl_data

        update_progress(db, eid, 16, "Analizando datos…", step=2)

        try:
            resolved_enrolments: List[Dict] = []
            for enr in etl_data["enrolments"]:
                resolved_username = ctx.username_map.get(enr["username"], enr["username"])
                resolved_enrolments.append({
                    **enr,
                    "username": resolved_username,
                })
            ctx.resolved_enrolments = resolved_enrolments

            ctx.missing_categories = []
            ctx.categories_to_relocate = []

            # Construir mapa idnumber → id numérico para resolver parents
            id_to_idnumber = {v["id"]: k for k, v in ctx.all_categories_map.items()}

            for cat in etl_data["categories"]:
                idn = cat.get("idnumber", "")
                if idn not in ctx.existing_cat_idnumbers:
                    ctx.missing_categories.append(cat)
                else:
                    existing = ctx.all_categories_map.get(idn, {})
                    actual_parent_id = existing.get("parent", 0)
                    expected_parent_idn = cat.get("parent", "")
                    actual_parent_idn = id_to_idnumber.get(actual_parent_id, "")

                    if expected_parent_idn and str(expected_parent_idn) != "0" and actual_parent_idn != expected_parent_idn:
                        ctx.categories_to_relocate.append({
                            "idnumber": idn,
                            "moodle_id": existing.get("id"),
                            "expected_parent_idn": expected_parent_idn,
                            "actual_parent_idn": actual_parent_idn or "root",
                            "cat_data": cat,
                        })

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

            if mode in ("users", "both"):
                ctx.users_to_create = [
                    u for u in etl_data["users"]
                    if u["username"] not in ctx.username_map
                    and u.get("email", "").endswith("@ut.edu.co")
                ]

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
