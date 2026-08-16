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
from app.pipeline.usuarios import elegir_usuario_mas_antiguo, elegir_usuario_mas_reciente
from app.services.errores_moodle import ErrorMoodleSobrecargado, es_moodle_sobrecargado
from app.services.manejador_errores_moodle import extraer_error, manejar_errores_moodle
from app.services.operaciones_moodle import ServicioMoodle

logger = logging.getLogger(__name__)


class IntegracionMoodle:
    def __init__(self, service: ServicioMoodle):
        self.servicio = service
        self.ultimo_error = ""
        self.ultimos_conflictos_correo: list[dict] = []

        # ------------------------------------------------------------------
        # Cursos
        # ------------------------------------------------------------------

    @manejar_errores_moodle(log_message="No se pudo reubicar categoría")
    async def reubicar_categoria(
        self, idnumber: str, moodle_id: int, target_parent_idn: str
    ) -> bool:
        await self.servicio.actualizar_categoria(
            category_id=moodle_id,
            parent_idnumber=target_parent_idn,
        )
        logger.info(f"Categoría {idnumber} reubicada bajo {target_parent_idn}")
        return True

    async def crear_curso(
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
            existing = await self.servicio.obtener_cursos(shortname=shortname)
            if existing:
                if recreate:
                    logger.info(f"Curso {shortname} ya existe y requiere recreate: borrando…")
                    await self.servicio.eliminar_cursos([shortname])
                    still = await self.servicio.obtener_cursos(shortname=shortname)
                    if still:
                        self.ultimo_error = (
                            f"Curso {shortname} no se pudo recrear: "
                            "el curso existente persiste tras el borrado"
                        )
                        logger.error(self.ultimo_error)
                        return False
                else:
                    if template_id:
                        logger.info(
                            f"Curso {shortname} ya existe, re-importando template {template_id}"
                        )
                        await self.servicio.importar_contenido_curso(
                            from_id=template_id,
                            to_id=int(existing[0]["id"]),
                        )
                    return True

            await self.servicio.crear_cursos(
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
            created = await self.servicio.obtener_cursos(shortname=shortname)
            if not created:
                self.ultimo_error = (
                    f"El curso {shortname} no fue creado a pesar de respuesta exitosa de la API"
                )
                logger.error(self.ultimo_error)
                return False
            logger.info(f"Curso creado (vacío): {shortname}")
            if template_id:
                try:
                    created = await self.servicio.obtener_cursos(shortname=shortname)
                    if created:
                        await self.servicio.importar_contenido_curso(
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
            if es_moodle_sobrecargado(e):
                raise ErrorMoodleSobrecargado(extraer_error(e)[:200]) from e
            logger.exception(f"Error al crear curso {shortname}: {e}")
            self.ultimo_error = extraer_error(e)
            return False

    @manejar_errores_moodle(log_message="Error al eliminar curso")
    async def eliminar_curso(self, shortname: str) -> bool:
        result = await self.servicio.eliminar_cursos([shortname])
        if result is None:
            logger.info(f"Curso {shortname} no encontrado, se omite (idempotente)")
            return True
        logger.info(f"Curso eliminado: {shortname}")
        return True

    @manejar_errores_moodle(log_message="Error al activar curso")
    async def activar_curso(self, shortname: str) -> bool:
        existing = await self.servicio.obtener_cursos(shortname=shortname)
        if not existing:
            self.ultimo_error = f"Curso no encontrado: {shortname}"
            return False
        await self.servicio.actualizar_cursos(
            [
                {
                    "shortname": shortname,
                    "visible": 1,
                }
            ]
        )
        verified = await self.servicio.obtener_cursos(shortname=shortname)
        if not verified or verified[0].get("visible") != 1:
            self.ultimo_error = f"Activación de {shortname} no se confirmó en Moodle"
            logger.error(self.ultimo_error)
            return False
        logger.info(f"Curso activado: {shortname}")
        return True

    @manejar_errores_moodle(log_message="Error al ocultar curso")
    async def ocultar_curso(self, shortname: str) -> bool:
        existing = await self.servicio.obtener_cursos(shortname=shortname)
        if not existing:
            self.ultimo_error = f"Curso no encontrado: {shortname}"
            return False
        await self.servicio.actualizar_cursos(
            [
                {
                    "shortname": shortname,
                    "visible": 0,
                }
            ]
        )
        verified = await self.servicio.obtener_cursos(shortname=shortname)
        if not verified or verified[0].get("visible") != 0:
            self.ultimo_error = f"Ocultamiento de {shortname} no se confirmó en Moodle"
            logger.error(self.ultimo_error)
            return False
        logger.info(f"Curso oculto: {shortname}")
        return True

    @manejar_errores_moodle(log_message="Error al renombrar curso")
    async def renombrar_curso(
        self, old_shortname: str, new_shortname: str, new_fullname: str
    ) -> bool:
        target = await self.servicio.obtener_cursos(shortname=new_shortname)
        if target:
            logger.warning(
                f"No se renombra {old_shortname} → {new_shortname}: "
                f"el destino ya existe como curso ID {target[0]['id']}"
            )
            return True

        existing = await self.servicio.obtener_cursos(shortname=old_shortname)
        if not existing:
            self.ultimo_error = f"Curso a renombrar no encontrado: {old_shortname}"
            logger.warning(self.ultimo_error)
            return False
        course_id = int(existing[0]["id"])
        await self.servicio.actualizar_cursos(
            [
                {
                    "id": course_id,
                    "shortname": new_shortname,
                    "fullname": new_fullname,
                }
            ]
        )
        verified = await self.servicio.obtener_cursos(shortname=new_shortname)
        if not verified:
            self.ultimo_error = f"Rename {old_shortname} → {new_shortname} no se confirmó en Moodle"
            logger.error(self.ultimo_error)
            return False
        logger.info(f"Curso renombrado: {old_shortname} → {new_shortname}")
        return True

        # ------------------------------------------------------------------
        # Usuarios (FASE 3)
        # ------------------------------------------------------------------

    async def _obtener_cursos_usuario(self, user_id) -> list | None:
        """Cursos matriculados del usuario; ``None`` si el webservice no permite
        la consulta (en ese caso no se puede evaluar la salvaguarda)."""
        try:
            result = await self.servicio._solicitar(
                "core_enrol_get_users_courses",
                {"userid": user_id},
                timeout=30.0,
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.warning(f"No se pudieron obtener cursos del usuario {user_id}: {e}")
            return None

    PREFIJO_TEMP = "zzdel_"
    LONGITUD_MAX_USUARIO = 100

    def _username_temporal(self, target: str) -> str:
        """Username temporal que libera el deseado antes de eliminar el duplicado."""
        return f"{self.PREFIJO_TEMP}{target}"[: self.LONGITUD_MAX_USUARIO]

    async def _renombrar_usuario(self, user_id, username: str) -> bool:
        """Renombra (username) una cuenta de Moodle por id."""
        try:
            await self.servicio.actualizar_usuarios([{"id": user_id, "username": username}])
            return True
        except Exception:
            logger.exception(f"Fallo al renombrar id={user_id} -> {username}")
            return False

    async def _quizas_cambiar_auth_externa(self, user: dict) -> tuple[bool, str]:
        """Pasa la cuenta conservada de base manual a la base de datos externa.

        Reglas:
          - El correo debe ser institucional (termina en INSTITUTIONAL_EMAIL_DOMAIN).
          - La cuenta NO debe estar en EXTERNAL_AUTH_EXCLUDED_USERS (admins).
          - El auth actual debe ser ``manual``; si ya es externo se deja intacto.
          - Si el auth actual no es conocido (nulo), no se fuerza el cambio.

        Retorna (auth_switched: bool, motivo: str).
        """
        current_auth = (user.get("auth") or "").strip().lower()
        email = (user.get("email") or "").strip().lower()
        username = (user.get("username") or "").strip().lower()

        if current_auth and current_auth != "manual":
            return False, f"ya {current_auth}"
        if not email.endswith(settings.INSTITUTIONAL_EMAIL_DOMAIN):
            return False, "manual (correo no institucional)"
        excluded = settings.claves_excluidas_auth_externa()
        if email in excluded or username in excluded:
            return False, "manual (admin excluido)"
        if not current_auth:
            return False, "manual (auth desconocido)"
        try:
            await self.servicio.actualizar_usuarios(
                [{"id": user.get("id"), "auth": settings.MOODLE_EXTERNAL_AUTH}]
            )
            return True, f"manual->{settings.MOODLE_EXTERNAL_AUTH}"
        except Exception:
            logger.exception(
                f"No se pudo cambiar auth de '{user.get('username', '')}' "
                f"(id={user.get('id')}) a '{settings.MOODLE_EXTERNAL_AUTH}'"
            )
            return False, "manual (fallo al cambiar auth)"

    async def _consolidar_duplicados(self, email: str, matches: list[dict]) -> dict | None:
        """Consolida cuentas que comparten email conservando la más antigua.

        1. Se conserva la cuenta MÁS ANTIGUA (la que tiene historial).
        2. Si la cuenta MÁS RECIENTE no tiene cursos, se toma su username (el
           deseado —el username real del usuario, que puede NO ser el prefijo
           del correo—), se renombra la cuenta antigua conservada a ese
           username (''la cuenta vieja queda renombrada'') y se elimina la
           cuenta reciente.
        3. Salvaguarda: si la reciente tiene cursos (o no se puede verificar
           porque el webservice no expone ``core_enrol_get_users_courses``),
           NO se elimina ni se renombra: queda en ``pending_review``.
        4. Si la cuenta conservada está en base manual (auth=manual) con correo
           institucional y no es admin, se pasa a la base de datos externa
           (auth=``MOODLE_EXTERNAL_AUTH``). Las no institucionales y los admins
           se dejan en base manual.

        Registra el resultado en ``last_email_conflicts`` y retorna la cuenta
        conservada (con su username actualizado si hubo rename), o None si no
        hay matches válidos.
        """
        mas_antiguo = elegir_usuario_mas_antiguo(matches)
        if mas_antiguo is None:
            return None
        duplicated = [u for u in matches if u is not mas_antiguo]
        if not duplicated:
            return mas_antiguo

        match_usernames = [u.get("username", "") for u in matches]

        deleted: list[str] = []
        pending_review: list[str] = []
        for user in duplicated:
            courses = await self._obtener_cursos_usuario(user.get("id"))
            if courses is None or courses:
                pending_review.append(user.get("username", ""))
            else:
                deleted.append(user.get("username", ""))

        renamed = ""
        mas_reciente = elegir_usuario_mas_reciente(duplicated)
        if (
            mas_reciente
            and mas_reciente.get("username") in deleted
            and mas_reciente.get("username") != mas_antiguo.get("username")
        ):
            target = mas_reciente.get("username")
            temp = self._username_temporal(target)
            newest_id = mas_reciente.get("id")
            # 1. Libera el username deseado renombrando la reciente a temp.
            if await self._renombrar_usuario(newest_id, temp):
                # 2. Renombra la cuenta antigua al username deseado.
                if await self._renombrar_usuario(mas_antiguo.get("id"), target):
                    renamed = target
                    mas_antiguo["username"] = target
                    deleted = [temp if u == target else u for u in deleted]
                else:
                    # Rollback: devuelve el username a la cuenta reciente.
                    await self._renombrar_usuario(newest_id, target)

        if deleted:
            try:
                await self.servicio.eliminar_usuarios(deleted)
            except Exception:
                logger.exception(f"Fallo al eliminar duplicados de {email}")
                pending_review.extend(deleted)
                deleted = []

        auth_switched, auth_reason = await self._quizas_cambiar_auth_externa(mas_antiguo)

        conflict = {
            "email": email,
            "usernames": match_usernames,
            "selected": mas_antiguo.get("username", ""),
            "selected_id": mas_antiguo.get("id"),
            "renamed": renamed,
            "deleted": deleted,
            "pending_review": pending_review,
            "auth_switched": auth_switched,
            "auth_reason": auth_reason,
        }
        self.ultimos_conflictos_correo.append(conflict)
        logger.warning(
            f"Email duplicado en Moodle {email}: usernames={conflict['usernames']}; "
            f"conservando '{conflict['selected']}' (id={conflict['selected_id']}); "
            f"renombrado='{renamed}'; eliminados={deleted}; "
            f"pendientes de revisión={pending_review}; auth: {auth_reason}"
        )
        return mas_antiguo

    async def encontrar_usuario_por_correo(self, email: str) -> dict | None:
        users = await self.servicio.obtener_usuarios("email", [email])
        if len(users) > 1:
            return await self._consolidar_duplicados(email, users)
        return users[0] if users else None

    @manejar_errores_moodle(
        log_message="Error al buscar usuarios por email en lote", default_return={}
    )
    async def encontrar_usuarios_por_correos(self, emails: list[str]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not emails:
            return result
        clean = [e.strip().lower() for e in emails if e and e.strip()]
        if not clean:
            return result
        users = await self.servicio.obtener_usuarios("email", clean)
        grouped: dict[str, list[dict]] = {}
        for u in users:
            email = (u.get("email") or "").strip().lower()
            if email:
                grouped.setdefault(email, []).append(u)

        self.ultimos_conflictos_correo = []
        for email, matches in grouped.items():
            mas_antiguo = await self._consolidar_duplicados(email, matches)
            if mas_antiguo is None:
                continue
            result[email] = mas_antiguo
        return result

    @manejar_errores_moodle(
        log_message="Error al buscar usuarios por username en lote", default_return={}
    )
    async def encontrar_usuarios_por_usernames(self, usernames: list[str]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not usernames:
            return result
        clean = [u.strip() for u in usernames if u and u.strip()]
        if not clean:
            return result
        users = await self.servicio.obtener_usuarios("username", clean)
        grouped: dict[str, list[dict]] = {}
        for u in users:
            uname = (u.get("username") or "").strip()
            if uname:
                grouped.setdefault(uname, []).append(u)
        for uname, matches in grouped.items():
            mas_antiguo = elegir_usuario_mas_antiguo(matches)
            if mas_antiguo is not None:
                result[uname] = mas_antiguo
        return result

    @manejar_errores_moodle(
        log_message="Error al buscar usuarios por cédula en lote", default_return={}
    )
    async def encontrar_usuarios_por_idnumbers(self, idnumbers: list[str]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not idnumbers:
            return result
        clean = [str(c).strip() for c in idnumbers if c and str(c).strip()]
        if not clean:
            return result
        users = await self.servicio.obtener_usuarios("idnumber", clean)
        grouped: dict[str, list[dict]] = {}
        for u in users:
            idn = (u.get("idnumber") or "").strip()
            if idn:
                grouped.setdefault(idn, []).append(u)
        for idn, matches in grouped.items():
            mas_antiguo = elegir_usuario_mas_antiguo(matches)
            if mas_antiguo is not None:
                result[idn] = mas_antiguo
        return result

    @staticmethod
    def es_usuario_activo(user: dict) -> bool:
        return not bool(int(user.get("suspended", 0)))

    async def crear_usuario_si_no_existe(self, user: dict) -> tuple[str | None, bool]:
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
            self.ultimo_error = f"Correo no institucional: {email}"
            logger.info(self.ultimo_error)
            return None, False

        username_esperado = email.split("@")[0]
        email_personal = (user.get("email_personal") or "").strip().lower()

        try:
            existing = await self.encontrar_usuario_por_correo(email)
        except Exception as e:
            if es_moodle_sobrecargado(e):
                raise ErrorMoodleSobrecargado(extraer_error(e)[:200]) from e
            self.ultimo_error = extraer_error(e)
            logger.exception(f"Error al buscar usuario por email {email}: {self.ultimo_error}")
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
                existing_by_personal = await self.encontrar_usuario_por_correo(email_personal)
            except Exception as e:
                if es_moodle_sobrecargado(e):
                    raise ErrorMoodleSobrecargado(extraer_error(e)[:200]) from e
                self.ultimo_error = extraer_error(e)
                logger.exception(
                    f"Error al buscar usuario por email personal {email_personal}: {self.ultimo_error}"
                )
                return None, False
            if existing_by_personal:
                return existing_by_personal.get("username", username_esperado), False

        try:
            existing_by_username = await self.servicio.obtener_usuario_por_username(
                username_esperado
            )
        except Exception as e:
            if es_moodle_sobrecargado(e):
                raise ErrorMoodleSobrecargado(extraer_error(e)[:200]) from e
            self.ultimo_error = extraer_error(e)
            logger.exception(
                f"Error al buscar usuario por username {username_esperado}: {self.ultimo_error}"
            )
            return None, False
        if existing_by_username:
            logger.info(
                f"Usuario {username_esperado} ya existe en Moodle (por username), no se crea"
            )
            return existing_by_username.get("username", username_esperado), False

        try:
            password = user.get("password", "")
            await self.servicio.crear_usuarios(
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
            created_user = await self.servicio.obtener_usuario_por_username(username_esperado)
            if not created_user:
                self.ultimo_error = f"El usuario {username_esperado} no fue creado a pesar de respuesta exitosa de la API"
                logger.error(self.ultimo_error)
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
            if es_moodle_sobrecargado(e):
                raise ErrorMoodleSobrecargado(extraer_error(e)[:200]) from e
            if getattr(e, "codigo_error", None) == "duplicateuser":
                logger.info(
                    f"Usuario {username_esperado} ya existe (race condition), recuperando ID"
                )
                try:
                    existing = await self.encontrar_usuario_por_correo(email)
                    if existing:
                        return existing.get("username", username_esperado), False
                except Exception as recovery_err:
                    logger.warning(
                        f"Recovery falló para usuario duplicado {username_esperado}: {recovery_err}"
                    )
                return username_esperado, False
            self.ultimo_error = extraer_error(e)
            logger.exception(f"Error al crear usuario {username_esperado}: {self.ultimo_error}")
            return None, False

    @manejar_errores_moodle(
        log_message="", default_return={"success": False, "reason": "Error del servidor Moodle"}
    )
    async def matricular_docente(
        self, username: str, course_shortname: str, course_map=None, courses=None, email: str = ""
    ) -> dict[str, Any]:
        result = await self.servicio.matricular_usuarios(
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
            self.ultimo_error = (
                str(err) if str(err).strip() else "Error desconocido del servidor Moodle"
            )
            return {"success": False, "username": username, "reason": self.ultimo_error}
        return {"success": True, "username": username, "reason": "enrolled"}
