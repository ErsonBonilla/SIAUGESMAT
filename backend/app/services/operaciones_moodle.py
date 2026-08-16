import logging
from typing import Any

from app.services.adaptador_moodle import AdaptadorMoodle, FabricaAdaptadorMoodle
from app.services.cliente_moodle import ClienteMoodle, generar_password_moodle
from app.services.errores_moodle import ErrorApiMoodle
from app.services.roles import rol_shortname_a_id

logger = logging.getLogger(__name__)

# Tamaño máximo de valores por consulta core_user_get_users_by_field.
# Con cientos de valores Moodle trunca la respuesta silenciosamente.
USERS_BATCH_SIZE = 100


class ServicioMoodle(ClienteMoodle):
    """
    Cliente asíncrono para la API REST de Moodle.

    Utiliza rate limiting y reintentos ante fallos transitorios.
    Todas las operaciones que involucran usuarios reciben o devuelven
    el **username** como identificador principal.
    """

    def __init__(
        self,
        token: str,
        base_url: str,
        adapter: AdaptadorMoodle | None = None,
        version: str | None = None,
    ):
        super().__init__(token, base_url, version)
        resolved_version = version or "3.9"
        self._adaptador = adapter or FabricaAdaptadorMoodle.crear(resolved_version)
        self._cache_categorias: list[dict] | None = None
        self._cache_cursos: dict[str, dict] | None = None

        # ------------------------------------------------------------------
        # Categorías
        # ------------------------------------------------------------------

    async def crear_categorias(self, categories: list[dict]) -> list[dict]:
        parent_idnumbers = {
            str(c["parent"]) for c in categories if c.get("parent") and str(c["parent"]) != "0"
        }
        parent_map: dict[str, int] = {}
        for pid in parent_idnumbers:
            parent_id = await self._obtener_id_categoria_por_idnumber(pid)
            if parent_id:
                parent_map[pid] = parent_id

        params = {}
        for i, cat in enumerate(categories):
            params[f"categories[{i}][name]"] = cat["name"]
            params[f"categories[{i}][idnumber]"] = cat["idnumber"]
            parent_val = cat.get("parent", 0)
            if str(parent_val) != "0":
                parent_val = parent_map.get(str(parent_val), 0)
            params[f"categories[{i}][parent]"] = parent_val
        result = await self._solicitar("core_course_create_categories", params)
        self._cache_categorias = None
        return result

    async def obtener_categorias(self, idnumber: str | None = None) -> list[dict]:
        if self._cache_categorias is None:
            self._cache_categorias = await self._solicitar("core_course_get_categories", {})
        if idnumber:
            return [c for c in self._cache_categorias if c.get("idnumber") == idnumber]
        return self._cache_categorias

    async def eliminar_categoria(self, category_id: int, recursive: bool = True) -> dict:
        params = {
            "categories[0][id]": category_id,
            "categories[0][recursive]": 1 if recursive else 0,
        }
        result = await self._solicitar("core_course_delete_categories", params)
        self._cache_categorias = None
        return result

    async def actualizar_categoria(
        self,
        category_id: int,
        parent_idnumber: str | None = None,
        name: str | None = None,
        idnumber: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"categories[0][id]": category_id}
        if parent_idnumber is not None:
            parent_id = await self._obtener_id_categoria_por_idnumber(parent_idnumber)
            if parent_id:
                params["categories[0][parent]"] = parent_id
            else:
                logger.warning(f"Parent idnumber {parent_idnumber} no encontrado en Moodle")
        if name is not None:
            params["categories[0][name]"] = name
        if idnumber is not None:
            params["categories[0][idnumber]"] = idnumber
        result = await self._solicitar("core_course_update_categories", params)
        self._cache_categorias = None
        return result

        # ------------------------------------------------------------------
        # Cursos
        # ------------------------------------------------------------------

    async def _obtener_id_categoria_por_idnumber(self, idnumber: str) -> int | None:
        cats = await self.obtener_categorias(idnumber=idnumber)
        if cats:
            return int(cats[0]["id"])
        return None

    async def crear_cursos(self, courses: list[dict]) -> list[dict]:
        cat_idnumbers = {c["categoryidnumber"] for c in courses if "categoryidnumber" in c}
        cat_map: dict[str, int] = {}
        for idnumber in cat_idnumbers:
            cat_id = await self._obtener_id_categoria_por_idnumber(idnumber)
            if not cat_id:
                parts = idnumber.rsplit("_", 1)
                if len(parts) == 2:
                    cat_id = await self._obtener_id_categoria_por_idnumber(parts[0])
            if not cat_id:
                cat_id = None
            if cat_id:
                cat_map[idnumber] = cat_id
            else:
                logger.error(
                    f"Categoría '{idnumber}' no encontrada en Moodle. "
                    f"El curso usará categoryid=0 (raíz)."
                )
                cat_map[idnumber] = 0

        params = {}
        for idx, course in enumerate(courses):
            cat_id = cat_map.get(course.get("categoryidnumber", ""), 0)
            params[f"courses[{idx}][shortname]"] = course["shortname"]
            params[f"courses[{idx}][fullname]"] = course["fullname"]
            params[f"courses[{idx}][categoryid]"] = cat_id
            if "format" in course:
                params[f"courses[{idx}][format]"] = course["format"]
            if "visible" in course:
                params[f"courses[{idx}][visible]"] = course["visible"]
            self._adaptador.construir_parametros_matriculacion_curso(params, course, idx)
        use_post = len(courses) > 10
        return await self._solicitar("core_course_create_courses", params, use_post=use_post)

    async def duplicar_curso(
        self,
        from_id: int,
        fullname: str,
        shortname: str,
        categoryid: int,
        visible: int = 1,
    ) -> dict:
        params = {
            "courseid": from_id,
            "fullname": fullname,
            "shortname": shortname,
            "categoryid": categoryid,
            "visible": visible,
            "options[0][name]": "activities",
            "options[0][value]": "1",
            "options[1][name]": "blocks",
            "options[1][value]": "1",
        }
        return await self._solicitar("core_course_duplicate_course", params)

    async def importar_contenido_curso(self, from_id: int, to_id: int) -> dict:
        params = {
            "importfrom": from_id,
            "importto": to_id,
            "deletecontent": 0,
            "options[0][name]": "activities",
            "options[0][value]": "1",
            "options[1][name]": "blocks",
            "options[1][value]": "1",
        }
        return await self._solicitar("core_course_import_course", params, timeout=120.0)

    async def actualizar_cursos(self, courses: list[dict]) -> dict | None:
        sin_id = [c for c in courses if not c.get("id")]
        mapa_ids: dict[str, int] = {}
        if sin_id:
            resueltos = await self.obtener_cursos_por_shortnames(
                [c.get("shortname", "") for c in sin_id]
            )
            mapa_ids = {
                c["shortname"]: int(c["id"])
                for c in resueltos
                if c.get("shortname") and c.get("id")
            }
        params = {}
        for i, course in enumerate(courses):
            course_id = course.get("id") or mapa_ids.get(course.get("shortname", ""))
            if not course_id:
                continue
            params[f"courses[{i}][id]"] = course_id
            for field in ("visible", "fullname", "shortname"):
                if field in course:
                    params[f"courses[{i}][{field}]"] = course[field]
        if not params:
            return None
        return await self._solicitar("core_course_update_courses", params)

    async def eliminar_cursos(self, shortnames: list[str], use_post: bool = True) -> dict | None:
        resueltos = await self.obtener_cursos_por_shortnames(shortnames)
        course_ids = [int(c["id"]) for c in resueltos if c.get("id")]
        if not course_ids:
            return None
        params = {}
        for i, cid in enumerate(course_ids):
            params[f"courseids[{i}]"] = cid
        use_post = use_post or len(course_ids) > 25
        return await self._solicitar("core_course_delete_courses", params, use_post=use_post)

    async def obtener_docentes_matriculados(
        self,
        course_id: int,
        teacher_emails: list[str],
        teacher_usernames: list[str] = None,
        teacher_idnumbers: list[str] = None,
    ) -> list[dict]:
        if not teacher_emails and not teacher_usernames and not teacher_idnumbers:
            return []
        users = await self._solicitar(
            "core_enrol_get_enrolled_users",
            params={
                "courseid": course_id,
                "options[0][name]": "withcapability",
                "options[0][value]": "moodle/course:manageactivities",
            },
        )
        target_emails = {e.lower() for e in teacher_emails if e}
        target_usernames = set(teacher_usernames) if teacher_usernames else set()
        target_idnumbers = set(teacher_idnumbers) if teacher_idnumbers else set()
        return [
            u
            for u in users
            if (target_emails and u.get("email", "").lower() in target_emails)
            or (target_usernames and u.get("username", "") in target_usernames)
            or (target_idnumbers and u.get("idnumber", "") in target_idnumbers)
        ]

    async def obtener_docentes_matriculados_con_acceso(self, course_id: int) -> list[dict]:
        return await self._solicitar(
            "core_enrol_get_enrolled_users",
            params={
                "courseid": course_id,
                "options[0][name]": "withcapability",
                "options[0][value]": "moodle/course:manageactivities",
            },
        )

    async def obtener_todos_usuarios_matriculados(self, course_id: int) -> list[dict]:
        """Devuelve TODOS los usuarios matriculados en un curso (sin filtrar por rol)."""
        return await self._solicitar(
            "core_enrol_get_enrolled_users",
            params={"courseid": course_id},
        )

    async def obtener_cursos(self, shortname: str | None = None) -> list[dict]:
        return await self._adaptador.obtener_cursos(shortname, self._solicitar)

    async def obtener_cursos_por_shortnames(self, shortnames: list[str]) -> list[dict]:
        if not shortnames:
            return []

        if self._cache_cursos is None:
            try:
                all_courses = await self.obtener_cursos()
                self._cache_cursos = {c["shortname"]: c for c in all_courses if c.get("shortname")}
            except Exception as e:
                logger.warning(f"Error poblando course_cache: {e}")
                self._cache_cursos = {}

        result = [self._cache_cursos[sn] for sn in shortnames if sn in self._cache_cursos]
        missing = [sn for sn in shortnames if sn not in self._cache_cursos]

        if not missing:
            return result

        for sn in missing:
            try:
                courses = await self.obtener_cursos_por_campo("shortname", sn)
                if courses:
                    self._cache_cursos[sn] = courses[0]
                    result.append(courses[0])
            except Exception:
                logger.warning(f"Error obteniendo curso shortname={sn}", exc_info=True)
        return result

        # ------------------------------------------------------------------
        # Auto-matriculación (self enrolment)
        # ------------------------------------------------------------------

    async def habilitar_automatriculacion(self, course_id: int) -> dict:
        return await self._adaptador.habilitar_automatriculacion(course_id, self._solicitar)

        # ------------------------------------------------------------------
        # Usuarios (basados exclusivamente en username)
        # ------------------------------------------------------------------

    async def crear_usuarios(self, users: list[dict]) -> list[dict]:
        params = {}
        for i, user in enumerate(users):
            params[f"users[{i}][username]"] = user["username"]
            params[f"users[{i}][auth]"] = "manual"
            params[f"users[{i}][firstname]"] = user["firstname"]
            params[f"users[{i}][lastname]"] = user["lastname"]
            params[f"users[{i}][email]"] = user["email"]
            use_createpassword = bool(user.get("createpassword"))
            if use_createpassword:
                params[f"users[{i}][createpassword]"] = "1"
            else:
                pwd = user.get("password", "")
                if not pwd or len(pwd) < 8:
                    pwd = generar_password_moodle()
                params[f"users[{i}][password]"] = pwd
            if user.get("city"):
                params[f"users[{i}][city]"] = user["city"]
            if user.get("description"):
                params[f"users[{i}][description]"] = user["description"]
            idn = user.get("idnumber") or user.get("cedula")
            if idn:
                params[f"users[{i}][idnumber]"] = str(idn)
        use_post = len(users) > 10
        return await self._solicitar("core_user_create_users", params, use_post=use_post)

    async def asignar_rol(self, user_id: int, role: object, context_id: int = 1) -> dict:
        role_id = role if isinstance(role, int) else rol_shortname_a_id(str(role))
        return await self._solicitar(
            "core_role_assign_role",
            params={
                "roleid": role_id,
                "userid": user_id,
                "contextid": context_id,
            },
        )

    async def eliminar_usuarios(self, usernames: list[str]) -> dict | None:
        user_ids = await self._obtener_ids_usuarios_por_usernames(usernames)
        if not user_ids:
            return None
        params = {}
        for i, uid in enumerate(user_ids):
            params[f"userids[{i}]"] = uid
        return await self._solicitar("core_user_delete_users", params)

    async def obtener_usuarios(self, field: str, values: list[str]) -> list[dict]:
        """Busca usuarios por campo fragmentando en lotes.

        ``core_user_get_users_by_field`` trunca silenciosamente la respuesta
        cuando se le pasan cientos de valores (se perdió ~26 % de los usuarios
        con ~1300 emails), así que se consulta por lotes de
        ``USERS_BATCH_SIZE`` y se agregan los resultados.
        """
        if not values:
            return []
        results: list[dict] = []
        for i in range(0, len(values), USERS_BATCH_SIZE):
            chunk = values[i : i + USERS_BATCH_SIZE]
            try:
                params: dict[str, Any] = {"field": field}
                for j, v in enumerate(chunk):
                    params[f"values[{j}]"] = v
                results.extend(
                    await self._solicitar(
                        "core_user_get_users_by_field", params, use_post=len(chunk) > 50
                    )
                )
            except ErrorApiMoodle as e:
                if getattr(e, "codigo_error", None) != "invalidparameter":
                    raise
                    # Un valor inválido invalida todo el lote: se reconsulta
                    # valor a valor para no perder los usuarios válidos.
                logger.warning(
                    f"get_users({field}): lote rechazado por invalidparameter, "
                    f"reconsultando {len(chunk)} valores individuales"
                )
                for v in chunk:
                    params: dict[str, Any] = {"field": field, "values[0]": v}
                    try:
                        results.extend(
                            await self._solicitar("core_user_get_users_by_field", params)
                        )
                    except ErrorApiMoodle as inner:
                        if getattr(inner, "codigo_error", None) != "invalidparameter":
                            raise
        return results

    async def obtener_usuario_por_username(self, username: str) -> dict | None:
        users = await self.obtener_usuarios("username", [username])
        return users[0] if users else None

    async def actualizar_usuarios(self, users: list[dict]) -> list[dict]:
        params = {}
        idx = 0
        for user in users:
            user_id = user.get("id")
            if not user_id and user.get("username"):
                resolved = await self.obtener_usuario_por_username(user["username"])
                if resolved:
                    user_id = int(resolved["id"])
            if not user_id:
                logger.warning(
                    f"No se pudo resolver ID para usuario '{user.get('username')}', se omite"
                )
                continue
            params[f"users[{idx}][id]"] = user_id
            if "email" in user:
                params[f"users[{idx}][email]"] = user["email"]
            if "username" in user:
                params[f"users[{idx}][username]"] = user["username"]
            if "auth" in user:
                params[f"users[{idx}][auth]"] = user["auth"]
            if "firstname" in user:
                params[f"users[{idx}][firstname]"] = user["firstname"]
            if "lastname" in user:
                params[f"users[{idx}][lastname]"] = user["lastname"]
            idx += 1
        if not params:
            return []
        return await self._solicitar("core_user_update_users", params)

    async def _obtener_ids_usuarios_por_usernames(self, usernames: list[str]) -> list[int]:
        if not usernames:
            return []
        users = await self.obtener_usuarios("username", usernames)
        return [int(u["id"]) for u in users]

        # ------------------------------------------------------------------
        # Consultas masivas
        # ------------------------------------------------------------------

    async def buscar_usuarios(self, term: str) -> list[dict]:
        """Busca usuarios por término (coincidencia exacta por campo).

        Usa core_user_get_users (Moodle 3.9), que requiere `criteria` y no
        soporta paginación ni substring. Consulta username, email, firstname
        y lastname en paralelo y devuelve la unión deduplicada por id.
        """
        term = (term or "").strip()
        if not term:
            return []
        found: dict[int, dict] = {}
        for key in ("username", "email", "firstname", "lastname"):
            try:
                result = await self._solicitar(
                    "core_user_get_users",
                    params={"criteria[0][key]": key, "criteria[0][value]": term},
                )
            except ErrorApiMoodle:
                continue
            users = result.get("users", []) if isinstance(result, dict) else []
            for user in users:
                if "lastlogin" not in user:
                    user["lastlogin"] = user.get("lastaccess", 0)
                found[int(user["id"])] = user
        return list(found.values())

    async def obtener_cursos_por_campo(self, field: str, value: str) -> list[dict]:
        result = await self._solicitar(
            "core_course_get_courses_by_field",
            params={"field": field, "value": value},
        )
        if isinstance(result, dict):
            return result.get("courses", [])
        return result

        # ------------------------------------------------------------------
        # Matriculación
        # ------------------------------------------------------------------

    async def matricular_usuarios(
        self, enrolments: list[dict], course_map: dict[str, int] = None, courses: list[dict] = None
    ) -> dict[str, Any]:
        missing_username = [e for e in enrolments if "username" not in e]
        if missing_username:
            logger.warning(
                f"{len(missing_username)} enrolment(s) sin 'username': {missing_username}"
            )
        usernames = [e["username"] for e in enrolments if "username" in e]
        shortnames = [e["course_shortname"] for e in enrolments]

        user_map = {}
        if usernames:
            users_info = await self.obtener_usuarios("username", usernames)
            user_map = {u["username"]: int(u["id"]) for u in users_info}

        emails_a_resolver = {
            e["email"] for e in enrolments if e.get("email") and e.get("username") not in user_map
        }
        if emails_a_resolver:
            por_email = await self.obtener_usuarios("email", sorted(emails_a_resolver))
            for u in por_email:
                if u.get("email") and u.get("id"):
                    user_map.setdefault(u["email"], int(u["id"]))

        if course_map is None:
            course_map = {}
            if shortnames:
                courses_info = (
                    courses if courses else await self.obtener_cursos_por_shortnames(shortnames)
                )
                course_map = {
                    c.get("shortname", ""): int(c["id"]) for c in courses_info if c.get("shortname")
                }

        params = {}
        idx = 0
        errors: list[str] = []
        for enrol in enrolments:
            user_id = user_map.get(enrol.get("username"))
            course_id = course_map.get(enrol.get("course_shortname"))
            if not user_id and not course_id:
                errors.append(
                    f"Usuario y curso no encontrados: {enrol.get('username')} / {enrol.get('course_shortname')}"
                )
                logger.error(f"No se pudo matricular: {errors[-1]}")
                continue
            if not user_id and enrol.get("email"):
                user_id = user_map.get(enrol["email"])
                if user_id:
                    user_map[enrol.get("username")] = user_id
                    logger.info(f"Enrol {enrol.get('username')} resuelto por email ({user_id})")
            if not user_id or not course_id:
                if not user_id:
                    msg = f"Usuario no encontrado en Moodle: {enrol.get('username')}"
                else:
                    msg = f"Curso no encontrado en Moodle: {enrol.get('course_shortname')}"
                errors.append(msg)
                logger.error(f"No se pudo matricular: {msg}")
                continue
            params[f"enrolments[{idx}][userid]"] = user_id
            params[f"enrolments[{idx}][courseid]"] = course_id
            params[f"enrolments[{idx}][roleid]"] = rol_shortname_a_id(enrol.get("role", "student"))
            idx += 1

        if not params:
            return {
                "success": False,
                "enrolled": 0,
                "failed": len(enrolments),
                "errors": errors,
                "error_codes": [],
            }

        use_post = idx > 50
        result = await self._solicitar("enrol_manual_enrol_users", params, use_post=use_post)
        api_errors = []
        api_error_codes = []
        if isinstance(result, list):
            for r in result:
                if isinstance(r, dict) and not r.get("result", True):
                    warnings_list = r.get("warnings", [])
                    for w in warnings_list:
                        msg = w.get("message", str(w)) if isinstance(w, dict) else str(w)
                        code = w.get("warningcode", "") if isinstance(w, dict) else ""
                        api_errors.append(msg)
                        api_error_codes.append(code)
                        logger.error(f"Moodle enrol error [{code}]: {msg}")
        if api_errors:
            return {
                "success": False,
                "enrolled": idx - len(api_errors),
                "failed": len(enrolments) - idx + len(api_errors),
                "errors": errors + api_errors,
                "error_codes": api_error_codes,
            }
        return {
            "success": True,
            "enrolled": idx,
            "failed": len(enrolments) - idx,
            "errors": errors,
        }

    async def desmatricular_usuarios(
        self, course_id: int, user_ids: list[int], role_id: int
    ) -> dict:
        params = {}
        for i, uid in enumerate(user_ids):
            params[f"enrolments[{i}][userid]"] = uid
            params[f"enrolments[{i}][courseid]"] = course_id
            params[f"enrolments[{i}][roleid]"] = role_id
        return await self._solicitar(
            "enrol_manual_unenrol_users", params, use_post=len(user_ids) > 10
        )
