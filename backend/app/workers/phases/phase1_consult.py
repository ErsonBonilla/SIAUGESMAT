import logging

from app.pipeline.users import (
    index_teachers,
    lookup_teacher_candidates,
    names_differ,
    normalize_name,
    resolve_users,
)
from app.repositories import log_repo
from app.repositories.execution_repo import touch_heartbeat, update_progress
from app.services.course_comparison import SIAUGESMAT_PATTERN
from app.services.error_messages import translate_error
from app.workers.phases.base import BasePhase, PhaseContext

logger = logging.getLogger(__name__)

# Re-export público del núcleo puro (los tests importan estos helpers aquí).
_normalize_name = normalize_name
_names_differ = names_differ


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

            etl_users = etl_data["users"]

            all_institutional = {u["email"] for u in etl_users if u.get("email")}
            all_personal = {
                u["email_personal"] for u in etl_users if u.get("email_personal")
            }

            def _persist_email_conflicts(integration=None):
                conflicts = getattr(integration, "last_email_conflicts", [])
                for conflict in conflicts:
                    log_repo.save_log(db, eid, "1", "identity_by_email_duplicate",
                                      conflict.get("email", ""), {
                                          "usernames": conflict.get("usernames", []),
                                          "selected": conflict.get("selected", ""),
                                          "selected_id": conflict.get("selected_id"),
                                          "criterion": "oldest",
                                      })

            institutional_map = await integration.find_users_by_emails(
                list(all_institutional)
            ) if all_institutional else {}
            _persist_email_conflicts(integration)
            personal_map = await integration.find_users_by_emails(
                list(all_personal - all_institutional)
            ) if all_personal else {}
            _persist_email_conflicts(integration)
            username_index = await integration.find_users_by_usernames(
                [u.get("username", "") for u in etl_users if u.get("username")]
            )
            idnumber_index = await integration.find_users_by_idnumbers(
                [u.get("cedula", "") for u in etl_users if u.get("cedula")]
            )

            username_map, user_events = resolve_users(
                etl_users,
                institutional_map,
                personal_map,
                username_index,
                idnumber_index,
            )
            for tipo, identifier, detail in user_events:
                if tipo == "user_resolved" and mode not in ("users", "both"):
                    continue
                log_repo.save_log(db, eid, "1", tipo, identifier, detail)
                if tipo == "user_identity_conflict":
                    logger.warning(
                        f"Conflicto de identidad {identifier}: ETL='{detail['etl_fullname']}' "
                        f"vs Moodle='{detail['moodle_fullname']}' "
                        f"(match por {detail['matched_by']})"
                    )
            ctx.username_map = username_map

            courses_by_sn = {c["shortname"]: c.get("fullname", "") for c in etl_data.get("courses", [])}
            for dup in etl_data.get("duplicates", []):
                log_repo.save_log(db, eid, "1", "duplicate_email", dup["email"], {
                    "usernames": dup.get("username", ""),
                    "course": dup.get("course_shortname", ""),
                    "fullname": courses_by_sn.get(dup.get("course_shortname", ""), ""),
                })

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

            courses_with_teacher: dict[str, str] = {}
            if mode in ("courses", "both"):
                teacher_index = index_teachers(etl_data["users"], etl_data["enrolments"])

                import asyncio
                sem = asyncio.Semaphore(10)

                async def _fetch_teacher(c, idx):
                    sn = c.get("shortname", "")
                    emails, usernames, idnumbers = lookup_teacher_candidates(sn, teacher_index)
                    async with sem:
                        teachers = await moodle_service.get_enrolled_teachers(
                            int(c["id"]), emails, teacher_usernames=usernames,
                            teacher_idnumbers=idnumbers,
                        )
                    if idx > 0 and idx % 25 == 0:
                        touch_heartbeat(db, eid)
                    if teachers:
                        return sn, teachers[0].get("username", "")
                    return sn, None

                tasks = [_fetch_teacher(c, i) for i, c in enumerate(ctx.existing_courses)]
                results = await asyncio.gather(*tasks)
                for sn, username in results:
                    if username:
                        courses_with_teacher[sn] = username
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
