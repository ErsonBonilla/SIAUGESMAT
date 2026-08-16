import logging
from typing import Any

from app.services.moodle_adapter import MoodleAdapter, MoodleAdapterFactory
from app.services.moodle_client import MoodleClient, generate_moodle_password
from app.services.moodle_errors import MoodleAPIError
from app.services.roles import role_shortname_to_id

logger = logging.getLogger(__name__)

# Tamaño máximo de valores por consulta core_user_get_users_by_field.
# Con cientos de valores Moodle trunca la respuesta silenciosamente.
USERS_BATCH_SIZE = 100


class MoodleService(MoodleClient):
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
        adapter: MoodleAdapter | None = None,
        version: str | None = None,
    ):
        super().__init__(token, base_url, version)
        resolved_version = version or "3.9"
        self._adapter = adapter or MoodleAdapterFactory.create(resolved_version)
        self._categories_cache: list[dict] | None = None
        self._course_cache: dict[str, dict] | None = None

    # ------------------------------------------------------------------
    # Categorías
    # ------------------------------------------------------------------
    async def create_categories(self, categories: list[dict]) -> list[dict]:
        parent_idnumbers = {
            str(c["parent"]) for c in categories if c.get("parent") and str(c["parent"]) != "0"
        }
        parent_map: dict[str, int] = {}
        for pid in parent_idnumbers:
            parent_id = await self._get_category_id_by_idnumber(pid)
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
        result = await self._request("core_course_create_categories", params)
        self._categories_cache = None
        return result

    async def get_categories(self, idnumber: str | None = None) -> list[dict]:
        if self._categories_cache is None:
            self._categories_cache = await self._request("core_course_get_categories", {})
        if idnumber:
            return [c for c in self._categories_cache if c.get("idnumber") == idnumber]
        return self._categories_cache

    async def delete_category(self, category_id: int, recursive: bool = True) -> dict:
        params = {
            "categories[0][id]": category_id,
            "categories[0][recursive]": 1 if recursive else 0,
        }
        result = await self._request("core_course_delete_categories", params)
        self._categories_cache = None
        return result

    async def update_category(
        self,
        category_id: int,
        parent_idnumber: str | None = None,
        name: str | None = None,
        idnumber: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"categories[0][id]": category_id}
        if parent_idnumber is not None:
            parent_id = await self._get_category_id_by_idnumber(parent_idnumber)
            if parent_id:
                params["categories[0][parent]"] = parent_id
            else:
                logger.warning(f"Parent idnumber {parent_idnumber} no encontrado en Moodle")
        if name is not None:
            params["categories[0][name]"] = name
        if idnumber is not None:
            params["categories[0][idnumber]"] = idnumber
        result = await self._request("core_course_update_categories", params)
        self._categories_cache = None
        return result

    # ------------------------------------------------------------------
    # Cursos
    # ------------------------------------------------------------------
    async def _get_category_id_by_idnumber(self, idnumber: str) -> int | None:
        cats = await self.get_categories(idnumber=idnumber)
        if cats:
            return int(cats[0]["id"])
        return None

    async def create_courses(self, courses: list[dict]) -> list[dict]:
        cat_idnumbers = {c["categoryidnumber"] for c in courses if "categoryidnumber" in c}
        cat_map: dict[str, int] = {}
        for idnumber in cat_idnumbers:
            cat_id = await self._get_category_id_by_idnumber(idnumber)
            if not cat_id:
                parts = idnumber.rsplit("_", 1)
                if len(parts) == 2:
                    cat_id = await self._get_category_id_by_idnumber(parts[0])
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
            self._adapter.build_create_course_enrolment_params(params, course, idx)
        use_post = len(courses) > 10
        return await self._request("core_course_create_courses", params, use_post=use_post)

    async def duplicate_course(
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
        return await self._request("core_course_duplicate_course", params)

    async def import_course_content(self, from_id: int, to_id: int) -> dict:
        params = {
            "importfrom": from_id,
            "importto": to_id,
            "deletecontent": 0,
            "options[0][name]": "activities",
            "options[0][value]": "1",
            "options[1][name]": "blocks",
            "options[1][value]": "1",
        }
        return await self._request("core_course_import_course", params, timeout=120.0)

    async def update_courses(self, courses: list[dict]) -> dict | None:
        params = {}
        for i, course in enumerate(courses):
            course_id = course.get("id")
            if not course_id:
                resolved = await self.get_courses(shortname=course.get("shortname", ""))
                if resolved:
                    course_id = int(resolved[0]["id"])
                else:
                    continue
            params[f"courses[{i}][id]"] = course_id
            for field in ("visible", "fullname", "shortname"):
                if field in course:
                    params[f"courses[{i}][{field}]"] = course[field]
        if not params:
            return None
        return await self._request("core_course_update_courses", params)

    async def delete_courses(self, shortnames: list[str], use_post: bool = True) -> dict | None:
        course_ids: list[int] = []
        for sn in shortnames:
            resolved = await self.get_courses(shortname=sn)
            if resolved:
                course_ids.append(int(resolved[0]["id"]))
        if not course_ids:
            return None
        params = {}
        for i, cid in enumerate(course_ids):
            params[f"courseids[{i}]"] = cid
        use_post = use_post or len(course_ids) > 25
        return await self._request("core_course_delete_courses", params, use_post=use_post)

    async def get_enrolled_teachers(
        self,
        course_id: int,
        teacher_emails: list[str],
        teacher_usernames: list[str] = None,
        teacher_idnumbers: list[str] = None,
    ) -> list[dict]:
        if not teacher_emails and not teacher_usernames and not teacher_idnumbers:
            return []
        users = await self._request(
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

    async def get_enrolled_teachers_with_access(self, course_id: int) -> list[dict]:
        return await self._request(
            "core_enrol_get_enrolled_users",
            params={
                "courseid": course_id,
                "options[0][name]": "withcapability",
                "options[0][value]": "moodle/course:manageactivities",
            },
        )

    async def get_all_enrolled_users(self, course_id: int) -> list[dict]:
        """Devuelve TODOS los usuarios matriculados en un curso (sin filtrar por rol)."""
        return await self._request(
            "core_enrol_get_enrolled_users",
            params={"courseid": course_id},
        )

    async def get_courses(self, shortname: str | None = None) -> list[dict]:
        return await self._adapter.get_courses(shortname, self._request)

    async def get_courses_by_shortnames(self, shortnames: list[str]) -> list[dict]:
        if not shortnames:
            return []

        if self._course_cache is None:
            try:
                all_courses = await self.get_courses()
                self._course_cache = {c["shortname"]: c for c in all_courses if c.get("shortname")}
            except Exception as e:
                logger.warning(f"Error poblando course_cache: {e}")
                self._course_cache = {}

        result = [self._course_cache[sn] for sn in shortnames if sn in self._course_cache]
        missing = [sn for sn in shortnames if sn not in self._course_cache]

        if not missing:
            return result

        for sn in missing:
            try:
                courses = await self.get_courses_by_field("shortname", sn)
                if courses:
                    self._course_cache[sn] = courses[0]
                    result.append(courses[0])
            except Exception:
                logger.warning(f"Error obteniendo curso shortname={sn}", exc_info=True)
        return result

    # ------------------------------------------------------------------
    # Auto-matriculación (self enrolment)
    # ------------------------------------------------------------------
    async def enable_self_enrolment(self, course_id: int) -> dict:
        return await self._adapter.enable_self_enrolment(course_id, self._request)

    # ------------------------------------------------------------------
    # Usuarios (basados exclusivamente en username)
    # ------------------------------------------------------------------
    async def create_users(self, users: list[dict]) -> list[dict]:
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
                    pwd = generate_moodle_password()
                params[f"users[{i}][password]"] = pwd
            if user.get("city"):
                params[f"users[{i}][city]"] = user["city"]
            if user.get("description"):
                params[f"users[{i}][description]"] = user["description"]
            idn = user.get("idnumber") or user.get("cedula")
            if idn:
                params[f"users[{i}][idnumber]"] = str(idn)
        use_post = len(users) > 10
        return await self._request("core_user_create_users", params, use_post=use_post)

    async def assign_role(self, user_id: int, role: object, context_id: int = 1) -> dict:
        role_id = role if isinstance(role, int) else role_shortname_to_id(str(role))
        return await self._request(
            "core_role_assign_role",
            params={
                "roleid": role_id,
                "userid": user_id,
                "contextid": context_id,
            },
        )

    async def delete_users(self, usernames: list[str]) -> dict | None:
        user_ids = await self._get_user_ids_by_usernames(usernames)
        if not user_ids:
            return None
        params = {}
        for i, uid in enumerate(user_ids):
            params[f"userids[{i}]"] = uid
        return await self._request("core_user_delete_users", params)

    async def get_users(self, field: str, values: list[str]) -> list[dict]:
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
                    await self._request(
                        "core_user_get_users_by_field", params, use_post=len(chunk) > 50
                    )
                )
            except MoodleAPIError as e:
                if getattr(e, "error_code", None) != "invalidparameter":
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
                        results.extend(await self._request("core_user_get_users_by_field", params))
                    except MoodleAPIError as inner:
                        if getattr(inner, "error_code", None) != "invalidparameter":
                            raise
        return results

    async def get_user_by_username(self, username: str) -> dict | None:
        users = await self.get_users("username", [username])
        return users[0] if users else None

    async def update_users(self, users: list[dict]) -> list[dict]:
        params = {}
        idx = 0
        for user in users:
            user_id = user.get("id")
            if not user_id and user.get("username"):
                resolved = await self.get_user_by_username(user["username"])
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
        return await self._request("core_user_update_users", params)

    async def _get_user_ids_by_usernames(self, usernames: list[str]) -> list[int]:
        if not usernames:
            return []
        users = await self.get_users("username", usernames)
        return [int(u["id"]) for u in users]

    # ------------------------------------------------------------------
    # Consultas masivas
    # ------------------------------------------------------------------
    async def search_users(self, term: str) -> list[dict]:
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
                result = await self._request(
                    "core_user_get_users",
                    params={"criteria[0][key]": key, "criteria[0][value]": term},
                )
            except MoodleAPIError:
                continue
            users = result.get("users", []) if isinstance(result, dict) else []
            for user in users:
                if "lastlogin" not in user:
                    user["lastlogin"] = user.get("lastaccess", 0)
                found[int(user["id"])] = user
        return list(found.values())

    async def get_courses_by_field(self, field: str, value: str) -> list[dict]:
        result = await self._request(
            "core_course_get_courses_by_field",
            params={"field": field, "value": value},
        )
        if isinstance(result, dict):
            return result.get("courses", [])
        return result

    # ------------------------------------------------------------------
    # Matriculación
    # ------------------------------------------------------------------
    async def enrol_users(
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
            users_info = await self.get_users("username", usernames)
            user_map = {u["username"]: int(u["id"]) for u in users_info}

        if course_map is None:
            course_map = {}
            if shortnames:
                courses_info = (
                    courses if courses else await self.get_courses_by_shortnames(shortnames)
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
                # Fallback: el username ETL puede no existir (usuario en Moodle
                # bajo otro username). Se resuelve por email institucional.
                by_email = await self.get_users("email", [enrol["email"]])
                if by_email:
                    user_id = int(by_email[0]["id"])
                    user_map[enrol.get("username")] = user_id
                    logger.info(
                        f"Enrol {enrol.get('username')} resuelto por email a "
                        f"{by_email[0].get('username')} ({user_id})"
                    )
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
            params[f"enrolments[{idx}][roleid]"] = role_shortname_to_id(
                enrol.get("role", "student")
            )
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
        result = await self._request("enrol_manual_enrol_users", params, use_post=use_post)
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

    async def unenrol_users(self, course_id: int, user_ids: list[int], role_id: int) -> dict:
        params = {}
        for i, uid in enumerate(user_ids):
            params[f"enrolments[{i}][userid]"] = uid
            params[f"enrolments[{i}][courseid]"] = course_id
            params[f"enrolments[{i}][roleid]"] = role_id
        return await self._request(
            "enrol_manual_unenrol_users", params, use_post=len(user_ids) > 10
        )
