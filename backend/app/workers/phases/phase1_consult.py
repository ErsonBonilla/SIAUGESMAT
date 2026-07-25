import logging
from typing import Dict, List, Set

from app.repositories import log_repo
from app.repositories.execution_repo import update_progress
from app.services.course_comparison import SIAUGESMAT_PATTERN
from app.services.error_messages import translate_error
from app.workers.phases.base import BasePhase, PhaseContext

logger = logging.getLogger(__name__)


class ConsultPhase(BasePhase):
    phase_name = "1"

    async def run(self, ctx: PhaseContext) -> None:
        db = ctx.db
        eid = ctx.execution_id
        mode = ctx.mode
        etl_data = ctx.etl_data
        moodle_service = ctx.moodle_service
        integration = ctx.integration

        try:
            update_progress(db, eid, 2, "Consultando categorías…", step=1)

            all_moodle_cats = await moodle_service.get_categories()
            ctx.all_categories_map = {
                c.get("idnumber", ""): c for c in all_moodle_cats if c.get("idnumber")
            }
            ctx.existing_cat_idnumbers = set(ctx.all_categories_map.keys())

            update_progress(db, eid, 5, "Consultando cursos…")

            all_courses = await moodle_service.get_courses()
            if not isinstance(all_courses, list):
                raise ValueError(
                    f"get_courses() devolvió {type(all_courses).__name__} "
                    f"en vez de list: {str(all_courses)[:200]}"
                )
            ctx.existing_courses = [
                c for c in all_courses
                if SIAUGESMAT_PATTERN.match(c.get("shortname", ""))
            ]

            update_progress(db, eid, 10, "Consultando usuarios…")

            username_map: Dict[str, str] = {}
            etl_users = etl_data["users"]

            all_institutional = {u["email"] for u in etl_users if u.get("email")}
            all_personal = {
                u["email_personal"] for u in etl_users if u.get("email_personal")
            }

            institutional_map = await integration.find_users_by_emails(
                list(all_institutional)
            ) if all_institutional else {}
            personal_map = await integration.find_users_by_emails(
                list(all_personal - all_institutional)
            ) if all_personal else {}

            for user in etl_users:
                moodle_user = (
                    institutional_map.get(user.get("email", "").strip().lower())
                    or personal_map.get(
                        (user.get("email_personal") or "").strip().lower()
                    )
                )
                if moodle_user:
                    username_map[user["username"]] = moodle_user["username"]
                    if mode in ("users", "both"):
                        log_repo.save_log(
                            db, eid, "1", "user_resolved",
                            moodle_user["username"],
                            {"email": user.get("email")},
                        )
            ctx.username_map = username_map

            log_repo.save_log(db, eid, "1", "phase1_complete", detail={
                "categories_found": len(ctx.existing_cat_idnumbers),
                "courses_found": len(ctx.existing_courses),
                "users_resolved": len(username_map),
            })
            logger.info(
                f"FASE 1: {len(ctx.existing_cat_idnumbers)} cats, "
                f"{len(ctx.existing_courses)} cursos, "
                f"{len(username_map)} usuarios resueltos"
            )
            update_progress(db, eid, 14, "Análisis de datos completado")

            courses_with_teacher: Set[str] = set()
            if mode in ("courses", "both"):
                teacher_emails_by_course: Dict[str, List[str]] = {}
                for enr in etl_data["enrolments"]:
                    sn = enr["course_shortname"]
                    user = next(
                        (u for u in etl_data["users"]
                         if u["username"] == enr["username"]), None
                    )
                    if user:
                        emails = [e for e in [user.get("email"), user.get("email_personal")] if e]
                        teacher_emails_by_course.setdefault(sn, []).extend(emails)

                for c in ctx.existing_courses:
                    sn = c.get("shortname", "")
                    emails = teacher_emails_by_course.get(sn, [])
                    teachers = await moodle_service.get_enrolled_teachers(int(c["id"]), emails)
                    if teachers:
                        courses_with_teacher.add(sn)
            ctx.courses_with_teacher = courses_with_teacher

            logger.info(
                f"FASE 1d: {len(courses_with_teacher)} cursos con editingteacher, "
                f"{len(ctx.existing_courses) - len(courses_with_teacher)} cursos huérfanos"
            )

        except Exception as e:
            logger.exception(f"Error en FASE 1 (consulta): {e}")
            log_repo.save_error(db, eid, "1", "", translate_error(e))
            ctx.metrics["total_errors"] += 1
            raise
