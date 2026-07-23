import logging
from typing import Dict

from app.core.config import settings
from app.repositories import log_repo
from app.repositories.execution_repo import save_checkpoint, update_progress
from app.services.error_messages import translate_error
from app.services.moodle import MoodleAPIError
from app.workers.phases.base import BasePhase, PhaseContext

logger = logging.getLogger(__name__)

CHECKPOINT_INTERVAL = 100


class ExecutePhase(BasePhase):
    phase_name = "3"

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
                ctx.phase3_progress = {"ops_completed": ops_count}
                save_checkpoint(db, eid, "3", {
                    "metrics": dict(metrics),
                    "username_map": ctx.username_map,
                    "phase3_progress": ctx.phase3_progress,
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

        update_progress(db, eid, 26, "Creando categorías…", step=3)

        try:
            if _do_courses() and ctx.missing_categories:
                for cat in ctx.missing_categories:
                    try:
                        await moodle_service.create_categories([cat])
                        metrics["categories_created"] += 1
                        log_repo.save_log(db, eid, "3", "category_created",
                                          cat["idnumber"],
                                          {"name": cat.get("name", ""), "parent": str(cat.get("parent", ""))})
                    except MoodleAPIError as e:
                        msg = f"Error al crear categoría {cat['idnumber']}: {e}"
                        logger.exception(msg)
                        metrics["total_errors"] += 1
                        log_repo.save_error(db, eid, "3", cat["idnumber"], msg)

            update_progress(db, eid, 30, "Eliminando cursos…")

            if _do_courses():
                if not settings.DEFAULT_COURSE_TEMPLATE:
                    raise ValueError(
                        "DEFAULT_COURSE_TEMPLATE no está configurada. "
                        "Defínela en el archivo .env."
                    )
                _template_cache: Dict[str, bool] = {}

                for sn in ctx.comparison.get("to_delete", []):
                    success = await integration.delete_course(sn)
                    if success:
                        metrics["courses_deleted"] += 1
                        log_repo.save_log(db, eid, "3", "course_deleted", sn, _course_detail(sn))
                    else:
                        metrics["total_errors"] += 1
                        log_repo.save_error(db, eid, "3", sn,
                                            f"Error al eliminar el curso '{sn}' en Moodle.")
                    _maybe_checkpoint()

                update_progress(db, eid, 34, "Activando cursos…")
                for sn in ctx.comparison.get("to_activate", []):
                    success = await integration.activate_course(sn)
                    if success:
                        metrics["courses_activated"] += 1
                        log_repo.save_log(db, eid, "3", "course_activated", sn, _course_detail(sn))
                    else:
                        metrics["total_errors"] += 1
                        log_repo.save_error(db, eid, "3", sn,
                                            f"Error al activar el curso '{sn}' en Moodle.")
                    _maybe_checkpoint()

                update_progress(db, eid, 38, "Ocultando cursos…")
                for sn in ctx.comparison.get("to_hide", []):
                    success = await integration.hide_course(sn)
                    if success:
                        metrics["courses_hidden"] += 1
                        log_repo.save_log(db, eid, "3", "course_hidden", sn, _course_detail(sn))
                    else:
                        metrics["total_errors"] += 1
                        log_repo.save_error(db, eid, "3", sn,
                                            f"Error al ocultar el curso '{sn}' en Moodle.")
                    _maybe_checkpoint()

                update_progress(db, eid, 42, "Renombrando cursos…")
                for item in ctx.comparison.get("to_update", []):
                    sn = item["shortname"]
                    course_data = courses_by_sn.get(sn)
                    if not course_data:
                        continue
                    success = await integration.rename_course(
                        old_shortname=item["old_shortname"],
                        new_shortname=sn,
                        new_fullname=course_data["fullname"],
                    )
                    if success:
                        log_repo.save_log(db, eid, "3", "course_renamed", sn, {
                            "old_shortname": item["old_shortname"],
                            "new_fullname": course_data.get("fullname", ""),
                            "old_fullname": courses_by_sn.get(item["old_shortname"], {}).get("fullname", ""),
                        })
                    else:
                        metrics["total_errors"] += 1
                        log_repo.save_error(
                            db, eid, "3", sn,
                            f"Error al renombrar curso: "
                            f"{item['old_shortname']} -> {sn}"
                        )

                update_progress(db, eid, 46, "Creando cursos…")
                for item in ctx.comparison.get("to_create", []):
                    sn = item["shortname"]
                    course_data = courses_by_sn.get(sn)
                    if not course_data:
                        continue
                    template = (
                        item.get("template_shortname")
                        or course_data.get("templatecourse")
                    )
                    if template and template.startswith("PORTAFOLIO_"):
                        if template not in _template_cache:
                            try:
                                existing = await moodle_service.get_courses(
                                    shortname=template
                                )
                                _template_cache[template] = len(existing) > 0
                            except Exception as exc:
                                logger.warning(
                                    f"Error al verificar template '{template}': {exc}"
                                )
                                _template_cache[template] = False
                        if not _template_cache[template]:
                            original = template
                            logger.info(
                                f"Template '{template}' no encontrado en Moodle, "
                                f"usando plantilla genérica "
                                f"'{settings.DEFAULT_COURSE_TEMPLATE}'"
                            )
                            template = settings.DEFAULT_COURSE_TEMPLATE
                            log_repo.save_log(db, eid, "3", "template_not_found", sn, {
                                "template_shortname": original,
                                "fallback": settings.DEFAULT_COURSE_TEMPLATE,
                            })
                    success = await integration.create_course(
                        shortname=sn,
                        fullname=course_data["fullname"],
                        category_idnumber=course_data["category_idnumber"],
                        template_shortname=template,
                    )
                    if success:
                        metrics["courses_created"] += 1
                    else:
                        metrics["total_errors"] += 1
                        log_repo.save_error(db, eid, "3", sn,
                                            f"Error al crear el curso '{sn}' en Moodle.")
                    _maybe_checkpoint()

            update_progress(db, eid, 66, "Creando usuarios…")

            if _do_users() and ctx.users_to_create:
                for user in ctx.users_to_create:
                    username, created = await integration.create_user_if_not_exists(user)
                    if username:
                        if created:
                            metrics["users_created"] += 1
                            log_repo.save_log(
                                db, eid, "3",
                                "user_created_createpassword",
                                username,
                                _user_detail(user.get("username", "")),
                            )
                        ctx.username_map[user["username"]] = username
                    else:
                        metrics["total_errors"] += 1
                        log_repo.save_error(db, eid, "3", user.get("username", ""),
                                            f"Error al crear usuario: {user.get('email', '')}")
                    _maybe_checkpoint()

            update_progress(db, eid, 80, "Matriculando docentes…")

            if _do_courses():
                # Refrescar lista de cursos (incluye los recién creados) para resolver IDs
                all_courses = await moodle_service.get_courses()
                for enrol in ctx.resolved_enrolments:
                    result = await integration.enrol_teacher(
                        enrol["username"], enrol["course_shortname"],
                        courses=all_courses,
                    )
                    if result["success"]:
                        metrics["enrolments"] += 1
                        log_repo.save_log(db, eid, "3", "enrolment_ok",
                                          result["username"],
                                          {"course": enrol["course_shortname"],
                                           **_course_detail(enrol["course_shortname"]),
                                           **_user_detail(result["username"])})
                    else:
                        metrics["enrolment_errors"] += 1
                        metrics["total_errors"] += 1
                        log_repo.save_log(db, eid, "3", "enrolment_failed",
                                          enrol["username"],
                                          {"course": enrol["course_shortname"],
                                           "reason": result["reason"],
                                           **_course_detail(enrol["course_shortname"]),
                                           **_user_detail(enrol["username"])})
                    _maybe_checkpoint()

        except Exception as e:
            logger.exception(f"Error en FASE 3 (ejecución): {e}")
            log_repo.save_error(db, eid, "3", "", translate_error(e))
            metrics["total_errors"] += 1
            db.commit()
            raise

        db.commit()
