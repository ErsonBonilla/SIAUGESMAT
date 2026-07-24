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

from app.services.moodle import MoodleAPIError, MoodleService

logger = logging.getLogger(__name__)


class MoodleIntegration:

    def __init__(self, service: MoodleService):
        self.service = service
        self.last_error = ""

    # ------------------------------------------------------------------
    # Cursos
    # ------------------------------------------------------------------
    async def create_course(
        self,
        shortname: str,
        fullname: str,
        category_idnumber: str,
        template_id: Optional[int] = None,
        visible: int = 1,
    ) -> bool:
        """Crea un curso en Moodle. Si hay template_id, usa core_course_duplicate_course."""
        try:
            if template_id:
                cat_id = await self.service._get_category_id_by_idnumber(category_idnumber)
                await self.service.duplicate_course(
                    from_id=template_id,
                    fullname=fullname,
                    shortname=shortname,
                    categoryid=cat_id or 0,
                    visible=visible,
                )
                logger.info(f"Curso creado desde plantilla {template_id}: {shortname}")
            else:
                await self.service.create_courses([{
                    "shortname": shortname,
                    "fullname": fullname,
                    "categoryidnumber": category_idnumber,
                    "format": "onetopic",
                    "visible": visible,
                }])
                logger.info(f"Curso creado (vacío): {shortname}")
            return True
        except Exception as e:
            logger.exception(f"Error al crear curso {shortname}: {e}")
            self.last_error = getattr(e, 'spanish_message', str(e))
            return False

    async def delete_course(self, shortname: str) -> bool:
        """Elimina un curso en Moodle vía REST API."""
        try:
            await self.service.delete_courses([shortname])
            logger.info(f"Curso eliminado: {shortname}")
            return True
        except Exception as e:
            logger.exception(f"Error al eliminar curso {shortname}: {e}")
            self.last_error = getattr(e, 'spanish_message', str(e))
            return False

    async def activate_course(self, shortname: str) -> bool:
        """Activa un curso oculto (visible=0 → 1) vía REST API."""
        try:
            await self.service.update_courses([{
                "shortname": shortname,
                "visible": 1,
            }])
            logger.info(f"Curso activado: {shortname}")
            return True
        except Exception as e:
            logger.exception(f"Error al activar curso {shortname}: {e}")
            self.last_error = getattr(e, 'spanish_message', str(e))
            return False

    async def hide_course(self, shortname: str) -> bool:
        """Oculta un curso (visible=1 → 0) vía REST API."""
        try:
            await self.service.update_courses([{
                "shortname": shortname,
                "visible": 0,
            }])
            logger.info(f"Curso oculto: {shortname}")
            return True
        except Exception as e:
            logger.exception(f"Error al ocultar curso {shortname}: {e}")
            self.last_error = getattr(e, 'spanish_message', str(e))
            return False

    async def rename_course(
        self, old_shortname: str, new_shortname: str, new_fullname: str
    ) -> bool:
        """Renombra un curso (grupo cambiado) vía REST API."""
        try:
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
            logger.exception(f"Error al renombrar curso {old_shortname}: {e}")
            self.last_error = getattr(e, 'spanish_message', str(e))
            return False

    # ------------------------------------------------------------------
    # Usuarios (FASE 3)
    # ------------------------------------------------------------------
    async def find_user_by_email(self, email: str) -> Optional[Dict]:
        """Busca un usuario en Moodle por su email vía REST API."""
        users = await self.service.get_users("email", [email])
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
        users = await self.service.get_users("email", clean)
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
            logger.info(f"Correo no institucional, no se crea usuario: {email}")
            return None, False

        username_esperado = email.split("@")[0]
        email_personal = (user.get("email_personal") or "").strip().lower()

        # 1. Buscar por email institucional
        try:
            existing = await self.find_user_by_email(email)
        except Exception as e:
            logger.exception(f"Error al buscar usuario por email {email}: {getattr(e, 'spanish_message', str(e))}")
            return None, False
        if existing:
            return existing.get("username", username_esperado), False

        # 2. Buscar por email personal
        if email_personal:
            try:
                existing_by_personal = await self.find_user_by_email(email_personal)
            except Exception as e:
                logger.exception(f"Error al buscar usuario por email personal {email_personal}: {getattr(e, 'spanish_message', str(e))}")
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
            logger.exception(f"Error al crear usuario {username_esperado}: {getattr(e, 'spanish_message', str(e))}")
            return None, False

    async def enrol_teacher(self, username: str, course_shortname: str,
                             course_map=None, courses=None) -> Dict[str, Any]:
        """
        Matricula un profesor en un curso por su username.
        Si course_map (shortname→id) se provee, se reutiliza sin
        llamadas extra a la API (optimizacion para ETL).

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
                err = result.get("errors", ["error desconocido"])[0]
                return {
                    "success": False,
                    "username": username,
                    "reason": str(err),
                }
            return {
                "success": True,
                "username": username,
                "reason": "enrolled",
            }
        except Exception as e:
            return {
                "success": False,
                "username": username,
                "reason": getattr(e, 'spanish_message', str(e)),
            }


