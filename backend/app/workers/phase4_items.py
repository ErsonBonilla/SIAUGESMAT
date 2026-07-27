import asyncio
import logging
import uuid
from typing import Dict

from app.core.config import settings
from app.repositories.operation_repo import add_item, create_batch
from app.services.moodle import MoodleService
from app.workers.phase_common import (
    _acquire_advisory_lock,
    _get_pending_counts,
    _items_exist_for_execution,
    _run_async,
)

logger = logging.getLogger(__name__)


def _create_phase4_items(db, execution_id, ctx_data, modalidad) -> Dict[str, int]:
    if _items_exist_for_execution(db, execution_id, "4"):
        pending = _get_pending_counts(db, execution_id, "4")
        if pending:
            logger.info(f"Items FASE 4 ya existen con {sum(pending.values())} pendientes, retomando")
            return pending
        logger.info(f"Items FASE 4 ya existen y todos procesados, saltando creación")
        return {}
    if not _acquire_advisory_lock(db, execution_id, "4"):
        logger.info(f"Lock FASE 4 ya tomado para ejecución {execution_id}, otro worker crea los items")
        return {}

    counts: Dict[str, int] = {}
    users_to_create = ctx_data.get("users_to_create", [])
    resolved_enrolments = ctx_data.get("resolved_enrolments", [])

    def _batch_id(suffix):
        return f"etl_4_{suffix}_{execution_id}"

    if users_to_create:
        batch = create_batch(db, _batch_id("users"), "users", "create", len(users_to_create), modalidad)
        count = 0
        for user in users_to_create:
            username = user.get("email", "").split("@")[0] if user.get("email") else user.get("username", str(uuid.uuid4()))
            detail = {
                "action": "create_user", "execution_id": execution_id, "modalidad": modalidad,
                "username": user.get("username", username),
                "firstname": user.get("firstname", ""),
                "lastname": user.get("lastname", ""),
                "email": user.get("email", ""),
                "has_password": bool(user.get("password")),
                "cedula": user.get("cedula", ""),
                "city": user.get("city", ""),
                "description": user.get("description", ""),
                "email_personal": user.get("email_personal", ""),
            }
            identifier = user.get("username", username)
            add_item(db, batch.batch_id, identifier, detail)
            count += 1
        counts["create_users"] = count

    if resolved_enrolments:
        batch = create_batch(db, _batch_id("enrol"), "enrolments", "enrol", len(resolved_enrolments), modalidad)
        count = 0

        async def _resolve_course_map():
            moodle_config = settings.get_moodle_config(modalidad)
            ms = MoodleService(token=moodle_config["token"], base_url=moodle_config["url"],
                                version=moodle_config["version"])
            try:
                all_courses = await ms.get_courses()
                course_map = {c["shortname"]: int(c["id"]) for c in all_courses if c.get("shortname")}
                missing = [sn for sn in all_sns if sn and sn not in course_map]
                if missing:
                    BATCH = 5
                    for i in range(0, len(missing), BATCH):
                        chunk = missing[i:i + BATCH]
                        try:
                            resolved = await ms.get_courses_by_shortnames(chunk)
                            for c in resolved:
                                if c.get("shortname"):
                                    course_map[c["shortname"]] = int(c["id"])
                        except Exception:
                            for sn in chunk:
                                try:
                                    courses = await ms.get_courses_by_field("shortname", sn)
                                    if courses and courses[0].get("id"):
                                        course_map[sn] = int(courses[0]["id"])
                                except Exception:
                                    pass
                return course_map
            finally:
                await ms.close()

        all_sns = list({enrol.get("course_shortname", "") for enrol in resolved_enrolments if enrol.get("course_shortname")})
        try:
            course_map = _run_async(_resolve_course_map())
        except Exception as e:
            logger.warning(f"Error resolviendo course_map global: {e}, intentando por shortname")

            async def _resolve_fallback():
                moodle_config = settings.get_moodle_config(modalidad)
                ms = MoodleService(token=moodle_config["token"], base_url=moodle_config["url"],
                                    version=moodle_config["version"])
                try:
                    fallback_map = {}
                    BATCH = 5
                    for i in range(0, len(all_sns), BATCH):
                        chunk = all_sns[i:i + BATCH]
                        try:
                            resolved = await ms.get_courses_by_shortnames(chunk)
                            for c in resolved:
                                if c.get("shortname"):
                                    fallback_map[c["shortname"]] = int(c["id"])
                        except Exception:
                            for sn in chunk:
                                try:
                                    courses = await ms.get_courses_by_field("shortname", sn)
                                    if courses and courses[0].get("id"):
                                        fallback_map[sn] = int(courses[0]["id"])
                                except Exception:
                                    pass
                    return fallback_map
                finally:
                    await ms.close()

            course_map = _run_async(_resolve_fallback())

        for enrol in resolved_enrolments:
            username = enrol.get("username", "")
            course_sn = enrol.get("course_shortname", "")
            course_id = course_map.get(course_sn)
            detail = {
                "action": "enrol", "execution_id": execution_id, "modalidad": modalidad,
                "course_shortname": course_sn,
                "_course_id": course_id,
            }
            add_item(db, batch.batch_id, username, detail)
            count += 1
        counts["enrol"] = count

    db.commit()
    return counts
