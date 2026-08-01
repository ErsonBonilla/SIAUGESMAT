import logging
import unicodedata
from typing import Dict, List

from app.repositories import log_repo
from app.repositories.execution_repo import touch_heartbeat, update_progress
from app.services.course_comparison import SIAUGESMAT_PATTERN
from app.services.parsers.patterns import parse_shortname
from app.services.error_messages import translate_error
from app.workers.phases.base import BasePhase, PhaseContext

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normaliza un nombre para comparación: minúsculas y sin tildes."""
    text = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    ).lower()
    return " ".join(text.split())


def _names_differ(etl_name: str, moodle_name: str) -> bool:
    """Detecta si dos nombres de persona difieren significativamente."""
    a = _normalize_name(etl_name)
    b = _normalize_name(moodle_name)
    if not a or not b:
        return False
    if a == b:
        return False
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return True
    overlap = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    return overlap < 0.5


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
            username_index = await integration.find_users_by_usernames(
                [u.get("username", "") for u in etl_users if u.get("username")]
            )
            idnumber_index = await integration.find_users_by_idnumbers(
                [u.get("cedula", "") for u in etl_users if u.get("cedula")]
            )

            for user in etl_users:
                email_lookup = user.get("email", "").strip().lower()
                personal_lookup = (user.get("email_personal") or "").strip().lower()
                uname = user.get("username", "")
                cedula = user.get("cedula", "")

                moodle_user = institutional_map.get(email_lookup)
                matched_by = "email"
                if not moodle_user:
                    moodle_user = personal_map.get(personal_lookup)
                    matched_by = "email_personal"
                if not moodle_user:
                    moodle_user = username_index.get(uname)
                    matched_by = "username"
                if not moodle_user:
                    moodle_user = idnumber_index.get(str(cedula))
                    matched_by = "cedula"
                if not moodle_user:
                    continue

                resolved_username = moodle_user.get("username", "")
                if matched_by in ("username", "cedula"):
                    etl_name = f"{user.get('firstname') or ''} {user.get('lastname') or ''}".strip()
                    moodle_name = f"{moodle_user.get('firstname') or ''} {moodle_user.get('lastname') or ''}".strip()
                    if _names_differ(etl_name, moodle_name):
                        log_repo.save_log(db, eid, "1", "user_identity_conflict", uname, {
                            "email": email_lookup,
                            "etl_fullname": etl_name,
                            "moodle_fullname": moodle_name,
                            "matched_by": matched_by,
                        })
                        logger.warning(
                            f"Conflicto de identidad {uname}: ETL='{etl_name}' vs "
                            f"Moodle='{moodle_name}' (match por {matched_by})"
                        )
                        continue

                username_map[user["username"]] = resolved_username
                if mode in ("users", "both"):
                    log_repo.save_log(
                        db, eid, "1", "user_resolved",
                        resolved_username,
                        {"email": user.get("email"),
                         "firstname": user.get("firstname", ""),
                         "lastname": user.get("lastname", "")},
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

            courses_with_teacher: Dict[str, str] = {}
            if mode in ("courses", "both"):
                teacher_emails_by_course: Dict[str, List[str]] = {}
                teacher_emails_by_base_key: Dict[tuple, List[str]] = {}
                teacher_usernames_by_course: Dict[str, List[str]] = {}
                teacher_usernames_by_base_key: Dict[tuple, List[str]] = {}
                teacher_idnumbers_by_course: Dict[str, List[str]] = {}
                teacher_idnumbers_by_base_key: Dict[tuple, List[str]] = {}
                users_by_username = {u["username"]: u for u in etl_data["users"]}
                for enr in etl_data["enrolments"]:
                    sn = enr["course_shortname"]
                    user = users_by_username.get(enr["username"])
                    if user:
                        emails = [e for e in [user.get("email"), user.get("email_personal")] if e]
                        teacher_emails_by_course.setdefault(sn, []).extend(emails)
                        teacher_usernames_by_course.setdefault(sn, []).append(enr["username"])
                        cedula = user.get("cedula", "")
                        if cedula:
                            teacher_idnumbers_by_course.setdefault(sn, []).append(cedula)
                        parsed = parse_shortname(sn)
                        if parsed:
                            bk = (parsed["cat_prefix"], parsed["cod_prog"], parsed["semestre"],
                                  parsed["cod_curso"], parsed["grupo"])
                            teacher_emails_by_base_key.setdefault(bk, []).extend(emails)
                            teacher_usernames_by_base_key.setdefault(bk, []).append(enr["username"])
                            if cedula:
                                teacher_idnumbers_by_base_key.setdefault(bk, []).append(cedula)

                import asyncio
                sem = asyncio.Semaphore(10)

                async def _fetch_teacher(c, idx):
                    sn = c.get("shortname", "")
                    emails = teacher_emails_by_course.get(sn, [])
                    usernames = teacher_usernames_by_course.get(sn, [])
                    idnumbers = teacher_idnumbers_by_course.get(sn, [])
                    if not emails:
                        parsed = parse_shortname(sn)
                        if parsed:
                            bk = (parsed["cat_prefix"], parsed["cod_prog"], parsed["semestre"],
                                  parsed["cod_curso"], parsed["grupo"])
                            emails = teacher_emails_by_base_key.get(bk, [])
                            usernames = teacher_usernames_by_base_key.get(bk, [])
                            idnumbers = teacher_idnumbers_by_base_key.get(bk, [])
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
