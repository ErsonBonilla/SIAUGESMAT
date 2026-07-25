import logging
from typing import Dict

from app.repositories import log_repo
from app.repositories.execution_repo import update_progress, save_checkpoint, _should_pause
from app.services.error_messages import translate_error
from app.services.moodle import is_moodle_overloaded
from app.workers.phases.base import BasePhase, PhaseContext, MoodleOverloadedError

logger = logging.getLogger(__name__)

CHECKPOINT_INTERVAL = 100


class PeoplePhase(BasePhase):
    phase_name = "4"

    async def run(self, ctx: PhaseContext) -> None:
        db = ctx.db
        eid = ctx.execution_id
        mode = ctx.mode
        etl_data = ctx.etl_data
        moodle_service = ctx.moodle_service
        integration = ctx.integration
        metrics = ctx.metrics
        ops_count = 0

        def _maybe_checkpoint():
            nonlocal ops_count
            ops_count += 1
            if ops_count % CHECKPOINT_INTERVAL == 0:
                ctx.people_progress = {"ops_completed": ops_count}

        def _check_pause() -> bool:
            """Retorna True si la ejecución fue pausada (el caller debe salir)."""
            if _should_pause(db, eid):
                save_checkpoint(db, eid, "4_progress", {
                    "metrics": dict(metrics),
                    "username_map": ctx.username_map,
                    "people_progress": ctx.people_progress,
                })
                return True
            return False

        def _save_progress(data: dict):
            """Guarda progreso parcial sin marcar la fase como completada."""
            ctx.people_progress = data
            save_checkpoint(db, eid, "4_progress", {
                "metrics": dict(metrics),
                "username_map": ctx.username_map,
                "people_progress": data,
            })

        def _do_courses() -> bool:
            return mode in ("courses", "both")

        def _do_users() -> bool:
            return mode in ("users", "both")

        courses_by_sn = {c["shortname"]: c for c in etl_data["courses"]}
        users_dict = {u["username"]: u for u in etl_data["users"]}

        def _course_detail(sn: str) -> dict:
            c = courses_by_sn.get(sn, {})
            return {"fullname": c.get("fullname", ""), "category_idnumber": c.get("category_idnumber", "")}

        def _user_detail(username: str) -> dict:
            u = users_dict.get(username, {})
            return {
                "firstname": u.get("firstname", ""),
                "lastname": u.get("lastname", ""),
                "email": u.get("email", ""),
            }

        update_progress(db, eid, 65, "Creando usuarios…", step=4)

        try:
            if _do_users() and ctx.users_to_create:
                for user in ctx.users_to_create:
                    try:
                        username, created = await integration.create_user_if_not_exists(user)
                    except Exception as e:
                        if is_moodle_overloaded(e):
                            _save_progress({"stage": "users", "last_user": user.get("username", "")})
                            raise MoodleOverloadedError(str(e)[:200])
                    if _check_pause():
                        return
                    if username:
                        if created:
                            metrics["users_created"] += 1
                            log_repo.save_log(
                                db, eid, "4",
                                "user_created_createpassword",
                                username,
                                _user_detail(user.get("username", "")),
                            )
                        ctx.username_map[user["username"]] = username
                    else:
                        metrics["total_errors"] += 1
                        log_repo.save_error(db, eid, "4", user.get("username", ""),
                                            f"Error al crear usuario: {user.get('email', '')}")
                    _maybe_checkpoint()

            update_progress(db, eid, 72, "Matriculando docentes…", step=4)

            if _do_courses():
                try:
                    all_courses = await moodle_service.get_courses()
                except Exception as e:
                    if is_moodle_overloaded(e):
                        raise MoodleOverloadedError(str(e)[:200])
                    raise
                course_map = {c["shortname"]: int(c["id"]) for c in all_courses if c.get("shortname")}
                total_enrol = len(ctx.resolved_enrolments)
                enrol_count = 0
                for enrol in ctx.resolved_enrolments:
                    try:
                        result = await integration.enrol_teacher(
                            enrol["username"], enrol["course_shortname"],
                            course_map=course_map,
                        )
                    except Exception as e:
                        if is_moodle_overloaded(e):
                            _save_progress({"stage": "enrol", "enrol_count": enrol_count})
                            raise MoodleOverloadedError(str(e)[:200])
                    if _check_pause():
                        return
                    if result["success"]:
                        metrics["enrolments"] += 1
                        log_repo.save_log(db, eid, "4", "enrolment_ok",
                                          result["username"],
                                          {"course": enrol["course_shortname"],
                                           **_course_detail(enrol["course_shortname"]),
                                           **_user_detail(result["username"])})
                    else:
                        metrics["enrolment_errors"] += 1
                        metrics["total_errors"] += 1
                        log_repo.save_log(db, eid, "4", "enrolment_failed",
                                          enrol["username"],
                                          {"course": enrol["course_shortname"],
                                           "reason": result["reason"],
                                           **_course_detail(enrol["course_shortname"]),
                                           **_user_detail(enrol["username"])})
                    enrol_count += 1
                    if enrol_count % 500 == 0 or enrol_count == total_enrol:
                        update_progress(db, eid, 72 + int(enrol_count / total_enrol * 13),
                                        f"Matriculando docentes… ({enrol_count}/{total_enrol})", step=4)
                    _maybe_checkpoint()

        except Exception as e:
            if is_moodle_overloaded(e):
                _save_progress(ctx.people_progress or {})
                raise MoodleOverloadedError(str(e)[:200])
            logger.exception(f"Error en FASE 4 (personas): {e}")
            log_repo.save_error(db, eid, "4", "", translate_error(e))
            metrics["total_errors"] += 1
            db.commit()
            raise

        db.commit()
