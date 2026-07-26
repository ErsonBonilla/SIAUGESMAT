"""
Capa de integración con Moodle.

Contiene funciones de alto nivel que orquestan las operaciones necesarias
para cada paso del proceso ETL, utilizando el servicio MoodleService.
Centraliza la lógica de negocio relacionada con la API de Moodle,
como la creación condicional de categorías, cursos con plantillas,
gestión de usuarios y matriculación.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services.moodle import MoodleAPIError, MoodleOverloadedError, MoodleService, is_moodle_overloaded

logger = logging.getLogger(__name__)


def _extract_error(e: Exception) -> str:
    """Extrae el mensaje real de error anidado."""
    if hasattr(e, 'spanish_message'):
        return e.spanish_message
    if e.__cause__ and hasattr(e.__cause__, 'spanish_message'):
        return e.__cause__.spanish_message
    if hasattr(e, 'last_attempt'):
        try:
            inner = e.last_attempt.exception()
            if hasattr(inner, 'spanish_message'):
                return inner.spanish_message
            return str(inner)[:300]
        except Exception:
            pass
    return str(e)[:300]


class MoodleIntegration:

    def __init__(self, service: MoodleService):
        self.service = service
        self.last_error = ""

    # ------------------------------------------------------------------
    # Cursos
    # ------------------------------------------------------------------
    async def relocate_category(self, idnumber: str, moodle_id: int, target_parent_idn: str) -> bool:
        """Mueve una categoría existente a un parent correcto."""
        try:
            await self.service.update_category(
                category_id=moodle_id,
                parent_idnumber=target_parent_idn,
            )
            logger.info(f"Categoría {idnumber} reubicada bajo {target_parent_idn}")
            return True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            self.last_error = _extract_error(e)
            logger.warning(f"No se pudo reubicar categoría {idnumber}: {self.last_error}")
            return False

    async def create_course(
        self,
        shortname: str,
        fullname: str,
        category_idnumber: str,
        template_id: Optional[int] = None,
        visible: int = 1,
    ) -> bool:
        """Crea un curso vacío. Si ya existe, lo omite (chulo verde)."""
        try:
            existing = await self.service.get_courses(shortname=shortname)
            if existing:
                if template_id:
                    logger.info(f"Curso {shortname} ya existe, re-importando template {template_id}")
                    await self.service.import_course_content(
                        from_id=template_id,
                        to_id=int(existing[0]["id"]),
                    )
                return True

            await self.service.create_courses([{
                "shortname": shortname,
                "fullname": fullname,
                "categoryidnumber": category_idnumber,
                "format": "onetopic",
                "visible": visible,
            }])
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
                    logger.warning(f"Template {template_id} no se pudo importar a {shortname}: {imp_e}")
            return True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            logger.exception(f"Error al crear curso {shortname}: {e}")
            self.last_error = _extract_error(e)
            return False

    async def delete_course(self, shortname: str) -> bool:
        """Elimina un curso en Moodle vía REST API."""
        try:
            result = await self.service.delete_courses([shortname])
            if result is None:
                logger.warning(f"Curso {shortname} no encontrado, no se eliminó")
                return True
            logger.info(f"Curso eliminado: {shortname}")
            return True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            logger.exception(f"Error al eliminar curso {shortname}: {e}")
            self.last_error = _extract_error(e)
            return False

    async def activate_course(self, shortname: str) -> bool:
        """Activa un curso oculto (visible=0 → 1) vía REST API."""
        try:
            existing = await self.service.get_courses(shortname=shortname)
            if not existing:
                self.last_error = f"Curso no encontrado: {shortname}"
                return False
            await self.service.update_courses([{
                "shortname": shortname,
                "visible": 1,
            }])
            logger.info(f"Curso activado: {shortname}")
            return True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            logger.exception(f"Error al activar curso {shortname}: {e}")
            self.last_error = _extract_error(e)
            return False

    async def hide_course(self, shortname: str) -> bool:
        """Oculta un curso (visible=1 → 0) vía REST API."""
        try:
            existing = await self.service.get_courses(shortname=shortname)
            if not existing:
                self.last_error = f"Curso no encontrado: {shortname}"
                return False
            await self.service.update_courses([{
                "shortname": shortname,
                "visible": 0,
            }])
            logger.info(f"Curso oculto: {shortname}")
            return True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            logger.exception(f"Error al ocultar curso {shortname}: {e}")
            self.last_error = _extract_error(e)
            return False

    async def rename_course(
        self, old_shortname: str, new_shortname: str, new_fullname: str
    ) -> bool:
        """Renombra un curso (grupo cambiado) vía REST API.
        Si el nuevo shortname ya existe en Moodle, se omite el rename
        (el destino ya está en el estado deseado)."""
        try:
            # Verificar que el nuevo shortname no esté ocupado
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
            await self.service.update_courses([{
                "id": course_id,
                "shortname": new_shortname,
                "fullname": new_fullname,
            }])
            logger.info(f"Curso renombrado: {old_shortname} → {new_shortname}")
            return True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            logger.exception(f"Error al renombrar curso {old_shortname}: {e}")
            self.last_error = _extract_error(e)
            return False

    # ------------------------------------------------------------------
    # Usuarios (FASE 3)
    # ------------------------------------------------------------------
    async def find_user_by_email(self, email: str) -> Optional[Dict]:
        """Busca un usuario en Moodle por su email vía REST API."""
        try:
            users = await self.service.get_users("email", [email])
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            self.last_error = _extract_error(e)
            logger.exception(f"Error al buscar usuario por email {email}: {self.last_error}")
            return None
        if len(users) > 1:
            logger.warning(
                f"Múltiples usuarios con el mismo email {email}: "
                f"{[u.get('username') for u in users]}"
            )
        return users[0] if users else None

    async def find_users_by_emails(self, emails: List[str]) -> Dict[str, Dict]:
        """
        Resuelve usuarios por email en lote (una sola llamada API).

        Returns:
            Dict[email, user_dict] para los emails encontrados en Moodle.
        """
        result: Dict[str, Dict] = {}
        if not emails:
            return result
        clean = [e.strip().lower() for e in emails if e and e.strip()]
        if not clean:
            return result
        try:
            users = await self.service.get_users("email", clean)
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            self.last_error = _extract_error(e)
            logger.exception(f"Error al buscar usuarios por email en lote: {self.last_error}")
            return result
        for u in users:
            email = (u.get("email") or "").strip().lower()
            if email:
                result[email] = u
        return result

    @staticmethod
    def is_user_active(user: Dict) -> bool:
        """Un usuario se considera activo si no está suspendido."""
        return not bool(int(user.get("suspended", 0)))

    async def create_user_if_not_exists(self, user: Dict) -> Tuple[Optional[str], bool]:
        """
        Localiza o crea un usuario en Moodle.

        Retorna (username, created):
          - (username: str, True)  → usuario creado exitosamente.
          - (username: str, False) → usuario ya existía (encontrado por email).
          - (None, False)          → error o correo no institucional.

        Estrategia:
          1. Buscar por email institucional → si existe, devolver (username, False).
          2. Buscar por email personal → si existe, devolver (username, False).
          3. No existe → crear con password = cédula + forcepasswordchange → (username, True).
        """
        email = user.get("email", "").strip().lower()
        if not email.endswith("@ut.edu.co"):
            self.last_error = f"Correo no institucional: {email}"
            logger.info(self.last_error)
            return None, False

        username_esperado = email.split("@")[0]
        email_personal = (user.get("email_personal") or "").strip().lower()

        # 1. Buscar por email institucional
        try:
            existing = await self.find_user_by_email(email)
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            self.last_error = _extract_error(e)
            logger.exception(f"Error al buscar usuario por email {email}: {self.last_error}")
            return None, False
        if existing:
            return existing.get("username", username_esperado), False

        # 2. Buscar por email personal
        if email_personal:
            try:
                existing_by_personal = await self.find_user_by_email(email_personal)
            except Exception as e:
                if is_moodle_overloaded(e):
                    raise MoodleOverloadedError(_extract_error(e)[:200])
                self.last_error = _extract_error(e)
                logger.exception(f"Error al buscar usuario por email personal {email_personal}: {self.last_error}")
                return None, False
            if existing_by_personal:
                return existing_by_personal.get("username", username_esperado), False

        # 3. No existe → crear con password = cédula + forcepasswordchange
        try:
            password = user.get("password", str(user.get("cedula", "")))
            await self.service.create_users([{
                "username": username_esperado,
                "firstname": user.get("firstname", ""),
                "lastname": user.get("lastname", ""),
                "email": email,
                "password": password,
                "forcepasswordchange": 1,
                "city": user.get("city", ""),
                "description": user.get("description", ""),
            }])
            logger.info(f"Usuario creado: {username_esperado}")
            return username_esperado, True
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            if getattr(e, 'error_code', None) == "duplicateuser":
                logger.info(f"Usuario {username_esperado} ya existe (race condition), recuperando ID")
                try:
                    existing = await self.find_user_by_email(email)
                    if existing:
                        return existing.get("username", username_esperado), False
                except Exception as recovery_err:
                    logger.warning(f"Recovery falló para usuario duplicado {username_esperado}: {recovery_err}")
                return username_esperado, False
            self.last_error = _extract_error(e)
            logger.exception(f"Error al crear usuario {username_esperado}: {self.last_error}")
            return None, False

    async def enrol_teacher(self, username: str, course_shortname: str,
                             course_map=None, courses=None) -> Dict[str, Any]:
        """
        Matricula un profesor en un curso por su username.
        Si course_map (shortname→id) se provee, se reutiliza sin
        llamadas extra a la API (optimizacion para ETL).
        El parámetro courses solo se usa cuando course_map es None.

        Returns:
            Dict con: success (bool), username (str), reason (str)
        """
        try:
            result = await self.service.enrol_users([{
                "username": username,
                "course_shortname": course_shortname,
                "role": "editingteacher",
            }], course_map=course_map, courses=courses)
            if not result["success"]:
                error_codes = result.get("error_codes", [])
                if "alreadyenrolled" in error_codes:
                    logger.info(f"Usuario {username} ya matriculado en {course_shortname}, omitiendo")
                    return {
                        "success": True,
                        "username": username,
                        "reason": "already_enrolled",
                    }
                err = result.get("errors", ["error desconocido"])[0]
                self.last_error = str(err)
                return {
                    "success": False,
                    "username": username,
                    "reason": self.last_error,
                }
            return {
                "success": True,
                "username": username,
                "reason": "enrolled",
            }
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(_extract_error(e)[:200])
            self.last_error = _extract_error(e)
            return {
                "success": False,
                "username": username,
                "reason": self.last_error,
            }


