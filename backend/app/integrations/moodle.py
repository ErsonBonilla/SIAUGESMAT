"""
Capa de integración con Moodle.

Contiene funciones de alto nivel que orquestan las operaciones necesarias
para cada paso del proceso ETL, utilizando el servicio MoodleService.
Centraliza la lógica de negocio relacionada con la API de Moodle,
como la creación condicional de categorías, cursos con plantillas,
gestión de usuarios y matriculación.
"""

import logging
from typing import Any

from app.core.config import settings
from app.pipeline.users import pick_oldest_user
from app.services.moodle_error_handler import extract_error, handle_moodle_errors
from app.services.moodle_errors import MoodleOverloadedError, is_moodle_overloaded
from app.services.moodle_operations import MoodleService

logger = logging.getLogger(__name__)


class MoodleIntegration:
    def __init__(self, service: MoodleService):
        self.service = service
        self.last_error = ""
        self.last_email_conflicts: list[dict] = []

    # ------------------------------------------------------------------
    # Cursos
    # ------------------------------------------------------------------
    @handle_moodle_errors(log_message="No se pudo reubicar categoría")
    async def relocate_category(
        self, idnumber: str, moodle_id: int, target_parent_idn: str
    ) -> bool:
        await self.service.update_category(
            category_id=moodle_id,
            parent_idnumber=target_parent_idn,
        )
        logger.info(f"Categoría {idnumber} reubicada bajo {target_parent_idn}")
        return True

    async def create_course(
        self,
        shortname: str,
        fullname: str,
        category_idnumber: str,
        template_id: int | None = None,
        visible: int = 1,
        recreate: bool = False,
    ) -> bool:
        """Crea un curso vacío.

        Si ya existe y ``recreate`` es True, primero lo borra y luego lo crea
        desde cero (asegura contenido fresco incluso si el borrado previo del
        plan falló). En caso contrario, si ya existe, lo omite (chulo verde).
        """
        try:
            existing = await self.service.get_courses(shortname=shortname)
            if existing:
                if recreate:
                    logger.info(f"Curso {shortname} ya existe y requiere recreate: borrando…")
                    await self.service.delete_courses([shortname])
                    still = await self.service.get_courses(shortname=shortname)
                    if still:
                        self.last_error = (
                            f"Curso {shortname} no se pudo recrear: "
                            "el curso existente persiste tras el borrado"
                        )
                        logger.error(self.last_error)
                        return False
                else:
                    if template_id:
                        logger.info(
                            f"Curso {shortname} ya existe, re-importando template {template_id}"
                        )
                        await self.service.import_course_content(
                            from_id=template_id,
                            to_id=int(existing[0]["id"]),
                        )
                    return True

            await self.service.create_courses(
                [
                    {
                        "shortname": shortname,
                        "fullname": fullname,
                        "categoryidnumber": category_idnumber,
                        "format": settings.DEFAULT_COURSE_FORMAT,
                        "visible": visible,
                    }
                ]
            )
            created = await self.service.get_courses(shortname=shortname)
            if not created:
                self.last_error = (
                    f"El curso {shortname} no fue creado a pesar de respuesta exitosa de la API"
                )
                logger.error(self.last_error)
                return False
            logger.info(f"Curso creado (vacío): {shortname}")
            if template_id:
                try:
                    created = await self.service.get_courses(shortname=shortname)
                    if created:
                        await self.service.import_course_content(
                            from_id=template_id,
                            to_id=int(created[0]["id"]),
                        )
                        logger.info(f"Plantilla {template_id} importada a {shortname}")
                except Exception as imp_e:
                    logger.warning(
                        f"Template {template_id} no se pudo importar a {shortname}: {imp_e}"
                    )
            return True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(extract_error(e)[:200]) from e
            logger.exception(f"Error al crear curso {shortname}: {e}")
            self.last_error = extract_error(e)
            return False

    @handle_moodle_errors(log_message="Error al eliminar curso")
    async def delete_course(self, shortname: str) -> bool:
        result = await self.service.delete_courses([shortname])
        if result is None:
            logger.info(f"Curso {shortname} no encontrado, se omite (idempotente)")
            return True
        logger.info(f"Curso eliminado: {shortname}")
        return True

    @handle_moodle_errors(log_message="Error al activar curso")
    async def activate_course(self, shortname: str) -> bool:
        existing = await self.service.get_courses(shortname=shortname)
        if not existing:
            self.last_error = f"Curso no encontrado: {shortname}"
            return False
        await self.service.update_courses(
            [
                {
                    "shortname": shortname,
                    "visible": 1,
                }
            ]
        )
        verified = await self.service.get_courses(shortname=shortname)
        if not verified or verified[0].get("visible") != 1:
            self.last_error = f"Activación de {shortname} no se confirmó en Moodle"
            logger.error(self.last_error)
            return False
        logger.info(f"Curso activado: {shortname}")
        return True

    @handle_moodle_errors(log_message="Error al ocultar curso")
    async def hide_course(self, shortname: str) -> bool:
        existing = await self.service.get_courses(shortname=shortname)
        if not existing:
            self.last_error = f"Curso no encontrado: {shortname}"
            return False
        await self.service.update_courses(
            [
                {
                    "shortname": shortname,
                    "visible": 0,
                }
            ]
        )
        verified = await self.service.get_courses(shortname=shortname)
        if not verified or verified[0].get("visible") != 0:
            self.last_error = f"Ocultamiento de {shortname} no se confirmó en Moodle"
            logger.error(self.last_error)
            return False
        logger.info(f"Curso oculto: {shortname}")
        return True

    @handle_moodle_errors(log_message="Error al renombrar curso")
    async def rename_course(
        self, old_shortname: str, new_shortname: str, new_fullname: str
    ) -> bool:
        target = await self.service.get_courses(shortname=new_shortname)
        if target:
            logger.warning(
                f"No se renombra {old_shortname} → {new_shortname}: "
                f"el destino ya existe como curso ID {target[0]['id']}"
            )
            return True

        existing = await self.service.get_courses(shortname=old_shortname)
        if not existing:
            self.last_error = f"Curso a renombrar no encontrado: {old_shortname}"
            logger.warning(self.last_error)
            return False
        course_id = int(existing[0]["id"])
        await self.service.update_courses(
            [
                {
                    "id": course_id,
                    "shortname": new_shortname,
                    "fullname": new_fullname,
                }
            ]
        )
        verified = await self.service.get_courses(shortname=new_shortname)
        if not verified:
            self.last_error = f"Rename {old_shortname} → {new_shortname} no se confirmó en Moodle"
            logger.error(self.last_error)
            return False
        logger.info(f"Curso renombrado: {old_shortname} → {new_shortname}")
        return True

    # ------------------------------------------------------------------
    # Usuarios (FASE 3)
    # ------------------------------------------------------------------
    async def _get_user_courses(self, user_id) -> list | None:
        """Cursos matriculados del usuario; ``None`` si el webservice no permite
        la consulta (en ese caso no se puede evaluar la salvaguarda)."""
        try:
            result = await self.service._request(
                "core_enrol_get_users_courses",
                {"userid": user_id},
                timeout=30.0,
            )
            return result if isinstance(result, list) else []
        except Exception:
            return None

    async def _consolidate_duplicates(self, email: str, matches: list[dict]) -> dict | None:
        """Consolida cuentas que comparten email: conserva la más antigua y
        elimina las más recientes que no tengan cursos matriculados.

        El username de la cuenta conservada NO se renombra: se usa tal cual
        existe en Moodle. Solo se escriben dos cosas: eliminar duplicados
        recientes (si corresponde) y registrar el conflicto.

        Salvaguarda: si la cuenta duplicada tiene cursos (o no se puede
        verificar porque el webservice no expone ``core_enrol_get_users_courses``),
        NO se elimina y queda en ``pending_review``.

        Registra el resultado en ``last_email_conflicts`` y retorna la cuenta
        conservada (la más antigua), o None si no hay matches válidos.
        """
        oldest = pick_oldest_user(matches)
        if oldest is None:
            return None
        duplicated = [u for u in matches if u is not oldest]
        if not duplicated:
            return oldest

        deleted: list[str] = []
        pending_review: list[str] = []
        for user in duplicated:
            courses = await self._get_user_courses(user.get("id"))
            if courses is None or courses:
                pending_review.append(user.get("username", ""))
            else:
                deleted.append(user.get("username", ""))

        if deleted:
            try:
                await self.service.delete_users(deleted)
            except Exception:
                logger.exception(f"Fallo al eliminar duplicados de {email}")
                pending_review.extend(deleted)
                deleted = []

        conflict = {
            "email": email,
            "usernames": [u.get("username", "") for u in matches],
            "selected": oldest.get("username", ""),
            "selected_id": oldest.get("id"),
            "deleted": deleted,
            "pending_review": pending_review,
        }
        self.last_email_conflicts.append(conflict)
        logger.warning(
            f"Email duplicado en Moodle {email}: usernames={conflict['usernames']}; "
            f"conservando '{conflict['selected']}' (id={conflict['selected_id']}); "
            f"eliminados={deleted}; pendientes de revisión={pending_review}"
        )
        return oldest

    async def find_user_by_email(self, email: str) -> dict | None:
        users = await self.service.get_users("email", [email])
        if len(users) > 1:
            return await self._consolidate_duplicates(email, users)
        return users[0] if users else None

    @handle_moodle_errors(
        log_message="Error al buscar usuarios por email en lote", default_return={}
    )
    async def find_users_by_emails(self, emails: list[str]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not emails:
            return result
        clean = [e.strip().lower() for e in emails if e and e.strip()]
        if not clean:
            return result
        users = await self.service.get_users("email", clean)
        grouped: dict[str, list[dict]] = {}
        for u in users:
            email = (u.get("email") or "").strip().lower()
            if email:
                grouped.setdefault(email, []).append(u)

        self.last_email_conflicts = []
        for email, matches in grouped.items():
            oldest = await self._consolidate_duplicates(email, matches)
            if oldest is None:
                continue
            result[email] = oldest
        return result

    @handle_moodle_errors(
        log_message="Error al buscar usuarios por username en lote", default_return={}
    )
    async def find_users_by_usernames(self, usernames: list[str]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not usernames:
            return result
        clean = [u.strip() for u in usernames if u and u.strip()]
        if not clean:
            return result
        users = await self.service.get_users("username", clean)
        grouped: dict[str, list[dict]] = {}
        for u in users:
            uname = (u.get("username") or "").strip()
            if uname:
                grouped.setdefault(uname, []).append(u)
        for uname, matches in grouped.items():
            oldest = pick_oldest_user(matches)
            if oldest is not None:
                result[uname] = oldest
        return result

    @handle_moodle_errors(
        log_message="Error al buscar usuarios por cédula en lote", default_return={}
    )
    async def find_users_by_idnumbers(self, idnumbers: list[str]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not idnumbers:
            return result
        clean = [str(c).strip() for c in idnumbers if c and str(c).strip()]
        if not clean:
            return result
        users = await self.service.get_users("idnumber", clean)
        grouped: dict[str, list[dict]] = {}
        for u in users:
            idn = (u.get("idnumber") or "").strip()
            if idn:
                grouped.setdefault(idn, []).append(u)
        for idn, matches in grouped.items():
            oldest = pick_oldest_user(matches)
            if oldest is not None:
                result[idn] = oldest
        return result

    @staticmethod
    def is_user_active(user: dict) -> bool:
        return not bool(int(user.get("suspended", 0)))

    async def create_user_if_not_exists(self, user: dict) -> tuple[str | None, bool]:
        """
        Localiza o crea un usuario en Moodle.

        Importante: el usuario encontrado por email se usa tal cual, el username
        en Moodle NUNCA se renombra (ni siquiera cuando difiere del prefijo del
        correo). Solo se crea un usuario nuevo —con el prefijo del email como
        username— cuando no existe ninguno.

        Retorna (username, created):
          - (username: str, True)  → usuario creado exitosamente.
          - (username: str, False) → usuario ya existía (encontrado por email).
          - (None, False)          → error o correo no institucional.
        """
        email = user.get("email", "").strip().lower()
        if not email.endswith(settings.INSTITUTIONAL_EMAIL_DOMAIN):
            self.last_error = f"Correo no institucional: {email}"
            logger.info(self.last_error)
            return None, False

        username_esperado = email.split("@")[0]
        email_personal = (user.get("email_personal") or "").strip().lower()

        try:
            existing = await self.find_user_by_email(email)
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(extract_error(e)[:200]) from e
            self.last_error = extract_error(e)
            logger.exception(f"Error al buscar usuario por email {email}: {self.last_error}")
            return None, False
        if existing:
            existing_username = existing.get("username", "")
            if existing_username and existing_username != username_esperado:
                logger.info(
                    f"Usuario encontrado por email {email} con username '{existing_username}' "
                    f"(esperado '{username_esperado}'). Se conserva el username de Moodle "
                    f"para preservar historial de cursos."
                )
            return existing_username if existing_username else username_esperado, False

        if email_personal:
            try:
                existing_by_personal = await self.find_user_by_email(email_personal)
            except Exception as e:
                if is_moodle_overloaded(e):
                    raise MoodleOverloadedError(extract_error(e)[:200]) from e
                self.last_error = extract_error(e)
                logger.exception(
                    f"Error al buscar usuario por email personal {email_personal}: {self.last_error}"
                )
                return None, False
            if existing_by_personal:
                return existing_by_personal.get("username", username_esperado), False

        try:
            existing_by_username = await self.service.get_user_by_username(username_esperado)
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(extract_error(e)[:200]) from e
            self.last_error = extract_error(e)
            logger.exception(
                f"Error al buscar usuario por username {username_esperado}: {self.last_error}"
            )
            return None, False
        if existing_by_username:
            logger.info(
                f"Usuario {username_esperado} ya existe en Moodle (por username), no se crea"
            )
            return existing_by_username.get("username", username_esperado), False

        try:
            password = user.get("password", str(user.get("cedula", "")))
            await self.service.create_users(
                [
                    {
                        "username": username_esperado,
                        "firstname": user.get("firstname", ""),
                        "lastname": user.get("lastname", ""),
                        "email": email,
                        "password": password,
                        "cedula": user.get("cedula", ""),
                        "forcepasswordchange": 1,
                        "city": user.get("city", ""),
                        "description": user.get("description", ""),
                    }
                ]
            )
            created_user = await self.service.get_user_by_username(username_esperado)
            if not created_user:
                self.last_error = f"El usuario {username_esperado} no fue creado a pesar de respuesta exitosa de la API"
                logger.error(self.last_error)
                return None, False
            created_auth = (created_user.get("auth") or "").strip().lower()
            if created_auth and created_auth != "manual":
                logger.warning(
                    f"El usuario {username_esperado} quedó con auth='{created_auth}' "
                    f"(esperado 'manual'). No se intenta crear en otra base de datos."
                )
            logger.info(f"Usuario creado: {username_esperado}")
            return username_esperado, True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(extract_error(e)[:200]) from e
            if getattr(e, "error_code", None) == "duplicateuser":
                logger.info(
                    f"Usuario {username_esperado} ya existe (race condition), recuperando ID"
                )
                try:
                    existing = await self.find_user_by_email(email)
                    if existing:
                        return existing.get("username", username_esperado), False
                except Exception as recovery_err:
                    logger.warning(
                        f"Recovery falló para usuario duplicado {username_esperado}: {recovery_err}"
                    )
                return username_esperado, False
            self.last_error = extract_error(e)
            logger.exception(f"Error al crear usuario {username_esperado}: {self.last_error}")
            return None, False

    @handle_moodle_errors(
        log_message="", default_return={"success": False, "reason": "Error del servidor Moodle"}
    )
    async def enrol_teacher(
        self, username: str, course_shortname: str, course_map=None, courses=None, email: str = ""
    ) -> dict[str, Any]:
        result = await self.service.enrol_users(
            [
                {
                    "username": username,
                    "course_shortname": course_shortname,
                    "role": "editingteacher",
                    "email": email,
                }
            ],
            course_map=course_map,
            courses=courses,
        )
        if not result["success"]:
            error_codes = result.get("error_codes", [])
            if "alreadyenrolled" in error_codes:
                logger.info(f"Usuario {username} ya matriculado en {course_shortname}, omitiendo")
                return {"success": True, "username": username, "reason": "already_enrolled"}
            err = result.get("errors", ["Error desconocido"])[0]
            self.last_error = (
                str(err) if str(err).strip() else "Error desconocido del servidor Moodle"
            )
            return {"success": False, "username": username, "reason": self.last_error}
        return {"success": True, "username": username, "reason": "enrolled"}
