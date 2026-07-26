"""
Cliente para la API REST de Moodle.

Encapsula las llamadas a los servicios web de Moodle necesarias para
la gestión de cursos, categorías, usuarios y matrículas. Incluye rate
limiting, reintentos automáticos y manejo de errores.

Las operaciones de usuario se basan **exclusivamente en el username**,
aprovechando la capacidad de la API de Moodle (3.8, 3.9+, 5.x) para
recibir tanto IDs numéricos como nombres de usuario.
"""

import asyncio
import logging
import secrets
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    before_log,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.services.moodle_adapter import (
    MoodleAdapter,
    MoodleAdapterFactory,
    role_shortname_to_id,
)
from app.services.rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: BaseException) -> bool:
    """Solo reintenta errores HTTP 5xx (servidor) o errores de Moodle retryables."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code >= 500
    if isinstance(exception, httpx.HTTPError):
        return True
    if isinstance(exception, MoodleAPIError):
        return exception.is_retryable
    return False


class MoodleOverloadedError(Exception):
    """El servidor de Moodle está sobrecargado. Celery reintentará la tarea."""


def is_moodle_overloaded(e: BaseException) -> bool:
    """Retorna True si el error es transitorio (servidor sobrecargado, timeout, o errores DB de Moodle)."""
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code in (502, 503, 504)
    if isinstance(e, httpx.ConnectError):
        return True
    if isinstance(e, httpx.ReadTimeout):
        return True
    inner = e
    if hasattr(e, 'last_attempt'):
        try:
            inner = e.last_attempt.exception() or inner
        except Exception:
            pass
    if isinstance(inner, MoodleAPIError):
        if inner.error_code in ("invalidrecord", "storedfilenotcreated", "invalidcoursemodule"):
            return True
    msg = str(e).lower()
    return any(kw in msg for kw in ("gateway time-out", "connect error", "read timeout", "connection refused"))


def _generate_moodle_password(length: int = 14) -> str:
    """Genera una contraseña que cumple la política por defecto de Moodle 3.9:
    mínimo 8 chars, al menos 1 mayúscula, 1 minúscula, 1 dígito, 1 no alfanumérico."""
    import string as _string
    lower = secrets.choice(_string.ascii_lowercase)
    upper = secrets.choice(_string.ascii_uppercase)
    digit = secrets.choice(_string.digits)
    special = secrets.choice("!@#$%&*?")
    remaining = length - 4
    pool = _string.ascii_letters + _string.digits + "!@#$%&*?"
    rest = "".join(secrets.choice(pool) for _ in range(remaining))
    combined = list(lower + upper + digit + special + rest)
    secrets.SystemRandom().shuffle(combined)
    return "".join(combined)


class MoodleAPIError(Exception):
    """Excepción lanzada cuando la API de Moodle devuelve un error."""

    # Códigos de error de Moodle que NO deben reintentarse (permanentes).
    # NOTA: invalidrecord, storedfilenotcreated, invalidcoursemodule NO están aquí
    # porque is_moodle_overloaded() los trata como errores transitorios
    # de sobrecarga y los convierte en MoodleOverloadedError para Celery.
    NON_RETRYABLE_CODES = frozenset({
        "invalidparameter", "missingparam", "invaliduser", "invalidcourse",
        "cannotcreatesitecourse", "invalidtoken", "nopermissions",
        "accessexception", "contextlevelnotsupported",
        "duplicatedshortname", "alreadyenrolled", "enrolmentnotfound",
        "notenrolled", "cannotdeletecategory", "cannotdeletecourse",
        "couldnotassignrole", "missingcapability", "duplicateuser", "duplicatecourse",
        "valueofparamelementnotset",
    })

    # Mapa de códigos de error de Moodle a mensajes en español
    ERROR_CODES: Dict[str, str] = {
        "invalidparameter": "Parámetro inválido enviado a Moodle.",
        "invalidtoken": "Token de autenticación inválido. Verifique la configuración.",
        "accessexception": "No tiene permisos para realizar esta operación en Moodle.",
        "nopermissions": "No tiene permisos para realizar esta operación en Moodle.",
        "requireloginerror": "Se requiere autenticación para acceder a este recurso en Moodle.",
        "course_not_found": "El curso no existe en Moodle.",
        "category_not_found": "La categoría no existe en Moodle.",
        "user_not_found": "El usuario no existe en Moodle.",
        "duplicatecourse": "Ya existe un curso con ese código en Moodle.",
        "wsfunctionnotavailable": "La función solicitada no está disponible en esta versión de Moodle.",
        "contextlevelnotsupported": "El nivel de contexto solicitado no es soportado por Moodle.",
        "missingparam": "Falta un parámetro requerido en la solicitud a Moodle.",
        "invalidrecord": "El registro solicitado no existe en Moodle.",
        "invalidcourse": "El curso especificado es inválido en Moodle.",
        "invaliduser": "El usuario especificado es inválido en Moodle.",
        "cannotcreatesitecourse": "No se puede crear un curso a nivel de sitio en Moodle.",
        "coursecategorynotfound": "La categoría de curso no existe en Moodle.",
        "enrol_cannot_usepregroup": "No se puede usar un grupo preexistente para esta matriculación.",
        "enrol_notenrollable": "El método de matriculación no está disponible en el curso.",
        "group_not_found": "El grupo no existe en Moodle.",
    }

    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.error_code = error_code

    @property
    def is_retryable(self) -> bool:
        """Un error es retryable si NO es un código de error permanente."""
        return self.error_code not in self.NON_RETRYABLE_CODES

    @property
    def spanish_message(self) -> str:
        """Retorna el mensaje traducido al español si existe el código, o el original."""
        if self.error_code and self.error_code in self.ERROR_CODES:
            return self.ERROR_CODES[self.error_code]
        return str(self.args[0]) if self.args else "Error desconocido de Moodle."

    def __str__(self):
        return self.spanish_message


class MoodleService:
    """
    Cliente asíncrono para la API REST de Moodle.

    Utiliza rate limiting y reintentos ante fallos transitorios.
    Todas las operaciones que involucran usuarios reciben o devuelven
    el **username** como identificador principal.
    """

    def __init__(self, token: str, base_url: str, adapter: Optional[MoodleAdapter] = None, version: Optional[str] = None):
        if not token:
            raise ValueError("token es requerido para MoodleService")
        if not base_url:
            raise ValueError("base_url es requerido para MoodleService")
        self._token = token
        self._base_url = base_url.rstrip("/") + "/webservice/rest/server.php"
        resolved_version = version or "3.9"
        if settings.REDIS_URL:
            self._rate_limiter = RedisRateLimiter(
                rate=settings.MOODLE_MAX_REQUESTS_PER_SECOND,
                window=1,
            )
        else:
            from app.services.rate_limiter import RateLimiter
            self._rate_limiter = RateLimiter(
                rate=settings.MOODLE_MAX_REQUESTS_PER_SECOND,
                burst=settings.MOODLE_BURST_SIZE,
            )
        self._client = httpx.AsyncClient(timeout=settings.MOODLE_REQUEST_TIMEOUT)
        self._adapter = adapter or MoodleAdapterFactory.create(resolved_version)

    # ------------------------------------------------------------------
    # Método genérico para llamar a la API
    # ------------------------------------------------------------------
    @retry(
        retry=retry_if_exception(_is_retryable_error),
        stop=stop_after_attempt(settings.MOODLE_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.WARNING),
    )
    async def _request(self, wsfunction: str, params: Dict[str, Any], use_post: bool = False,
                       timeout: Optional[float] = None) -> Any:
        """Realiza una petición a la API de Moodle con rate limiting.
        Si use_post=True o la URL excede ~7KB, usa POST para evitar limitaciones de longitud.
        timeout: opcional, sobrescribe el timeout por defecto para operaciones largas (ej. import).
        Los errores de sobrecarga (502/503/504/invalidrecord) se convierten en MoodleOverloadedError."""
        await self._rate_limiter.acquire()

        payload = {
            "wstoken": self._token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
        }

        try:
            request_kwargs = {}
            if timeout is not None:
                request_kwargs["timeout"] = timeout
            if use_post:
                response = await self._client.post(
                    self._base_url, data={**payload, **params}, **request_kwargs
                )
            else:
                response = await self._client.get(
                    self._base_url, params={**payload, **params}, **request_kwargs
                )
            response.raise_for_status()
        except Exception as e:
            if is_moodle_overloaded(e):
                raise MoodleOverloadedError(str(e)[:200]) from e
            raise

        data = response.json()

        if data is not None and not isinstance(data, (dict, list)):
            raise MoodleAPIError(
                f"Respuesta inesperada de {wsfunction}: {str(data)[:300]}"
            )

        if isinstance(data, dict) and ("error" in data or "exception" in data):
            error_code = data.get("errorcode", "")
            error_msg = data.get("error") or data.get("exception") or data.get("message", "")
            logger.error(f"Moodle API error [{wsfunction}]: {error_code} — {error_msg}")
            exc = MoodleAPIError(
                data.get("error") or data.get("exception"),
                data.get("errorcode"),
            )
            if is_moodle_overloaded(exc):
                raise MoodleOverloadedError(str(exc)[:200]) from exc
            raise exc

        return data

    # ------------------------------------------------------------------
    # Categorías
    # ------------------------------------------------------------------
    async def create_categories(self, categories: List[Dict]) -> List[Dict]:
        """Crea una o varias categorías en Moodle, resolviendo parent idnumber a ID numérico."""
        parent_idnumbers = {
            str(c["parent"]) for c in categories
            if c.get("parent") and str(c["parent"]) != "0"
        }
        parent_map: Dict[str, int] = {}
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
        return await self._request("core_course_create_categories", params)

    async def get_categories(self, idnumber: Optional[str] = None) -> List[Dict]:
        """Busca categorías. Filtra localmente porque Moodle 3.9 ignora criteria."""
        result = await self._request("core_course_get_categories", {})
        if idnumber:
            return [c for c in result if c.get("idnumber") == idnumber]
        return result

    async def delete_category(self, category_id: int, recursive: bool = True) -> Dict:
        """Elimina una categoría por ID. Si recursive=True, borra subcategorías y cursos."""
        params = {
            "categories[0][id]": category_id,
            "categories[0][recursive]": 1 if recursive else 0,
        }
        return await self._request("core_course_delete_categories", params)

    async def update_category(self, category_id: int, parent_idnumber: Optional[str] = None,
                               name: Optional[str] = None, idnumber: Optional[str] = None) -> Dict:
        """Actualiza campos de una categoría (parent, name, idnumber)."""
        params: Dict[str, Any] = {"categories[0][id]": category_id}
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
        return await self._request("core_course_update_categories", params)

    # ------------------------------------------------------------------
    # Cursos
    # ------------------------------------------------------------------
    async def _get_category_id_by_idnumber(self, idnumber: str) -> Optional[int]:
        """Resuelve un idnumber de categoría a su ID numérico en Moodle."""
        cats = await self.get_categories(idnumber=idnumber)
        if cats:
            return int(cats[0]["id"])
        return None

    async def create_courses(self, courses: List[Dict]) -> List[Dict]:
        """Crea cursos en Moodle, resolviendo idnumber de categoría a ID numérico
        con fallback multi-nivel para compatibilidad con Moodle 3.9."""
        cat_idnumbers = {
            c["categoryidnumber"]
            for c in courses
            if "categoryidnumber" in c
        }
        cat_map: Dict[str, int] = {}
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
        idx = 0
        for course in courses:
            cat_id = cat_map.get(course.get("categoryidnumber", ""), 0)
            params[f"courses[{idx}][shortname]"] = course["shortname"]
            params[f"courses[{idx}][fullname]"] = course["fullname"]
            params[f"courses[{idx}][categoryid]"] = cat_id
            if "format" in course:
                params[f"courses[{idx}][format]"] = course["format"]
            if "visible" in course:
                params[f"courses[{idx}][visible]"] = course["visible"]
            self._adapter.build_create_course_enrolment_params(params, course, idx)
            idx += 1
        use_post = len(courses) > 10
        return await self._request("core_course_create_courses", params, use_post=use_post)

    async def duplicate_course(
        self, from_id: int, fullname: str, shortname: str,
        categoryid: int, visible: int = 1,
    ) -> Dict:
        """Crea un curso nuevo copiando contenido de una plantilla en una sola llamada.
        NOTA: No usado actualmente. El template se maneja con create_courses + import_course_content."""
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

    async def import_course_content(self, from_id: int, to_id: int) -> Dict:
        """Copia contenido (activities + blocks) desde un curso plantilla a un curso destino existente.
        Timeout de 120s porque la importación puede ser lenta con cursos grandes."""
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

    async def update_courses(self, courses: List[Dict]) -> Optional[Dict]:
        """Actualiza campos de cursos existentes, resolviendo shortname a ID si es necesario."""
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

    async def delete_courses(self, shortnames: List[str], use_post: bool = True) -> Optional[Dict]:
        """Elimina cursos resolviendo shortnames a IDs numéricos.
        Por defecto usa POST para soportar lotes grandes sin truncar URL."""
        course_ids: List[int] = []
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

    async def get_enrolled_teachers(self, course_id: int, teacher_emails: List[str]) -> List[Dict]:
        """Obtiene usuarios con rol editingteacher en un curso cuyos emails coincidan."""
        if not teacher_emails:
            return []
        users = await self._request(
            "core_enrol_get_enrolled_users",
            params={
                "courseid": course_id,
                "options[0][name]": "withcapability",
                "options[0][value]": "moodle/course:manageactivities",
            },
        )
        target = set(e.lower() for e in teacher_emails if e)
        return [u for u in users if u.get("email", "").lower() in target]

    async def get_courses(self, shortname: Optional[str] = None) -> List[Dict]:
        """Busca cursos por shortname. Si no se especifica, devuelve todos."""
        return await self._adapter.get_courses(shortname, self._request)

    async def get_courses_by_shortnames(self, shortnames: List[str]) -> List[Dict]:
        """Obtiene cursos por shortname.

        Para lotes pequeños (≤5) usa llamadas individuales vía
        core_course_get_courses_by_field. Para lotes grandes trae
        todos los cursos y filtra localmente."""
        if not shortnames:
            return []
        if len(shortnames) <= 5:
            result = []
            for sn in shortnames:
                try:
                    courses = await self.get_courses_by_field("shortname", sn)
                    result.extend(courses)
                except Exception:
                    logger.warning(f"Error obteniendo curso shortname={sn}", exc_info=True)
            return result
        try:
            all_courses = await self.get_courses()
        except Exception as e:
            logger.error(f"Error obteniendo todos los cursos para filtrar por shortnames: {e}")
            raise
        target = set(shortnames)
        return [c for c in all_courses if c.get("shortname") in target]

    # ------------------------------------------------------------------
    # Auto-matriculación (self enrolment)
    # ------------------------------------------------------------------
    async def enable_self_enrolment(self, course_id: int) -> Dict:
        """Habilita la auto-matriculación según la versión de Moodle.
        NOTA: No usado actualmente. La auto-matriculación se crea por defecto en Moodle 3.x."""
        return await self._adapter.enable_self_enrolment(course_id, self._request)

    # ------------------------------------------------------------------
    # Usuarios (basados exclusivamente en username)
    # ------------------------------------------------------------------
    async def create_users(self, users: List[Dict]) -> List[Dict]:
        """Crea usuarios en Moodle con soporte para forcepasswordchange.
        Cuando createpassword=1, Moodle 3.9 ignora el campo password
        y genera una contraseña que cumple su política de seguridad."""
        params = {}
        for i, user in enumerate(users):
            params[f"users[{i}][username]"] = user["username"]
            params[f"users[{i}][firstname]"] = user["firstname"]
            params[f"users[{i}][lastname]"] = user["lastname"]
            params[f"users[{i}][email]"] = user["email"]
            use_createpassword = bool(user.get("createpassword"))
            if use_createpassword:
                params[f"users[{i}][createpassword]"] = "1"
            else:
                pwd = user.get("password", "")
                if not pwd or len(pwd) < 8:
                    pwd = _generate_moodle_password()
                params[f"users[{i}][password]"] = pwd
            if user.get("city"):
                params[f"users[{i}][city]"] = user["city"]
            if user.get("description"):
                params[f"users[{i}][description]"] = user["description"]
        use_post = len(users) > 10
        return await self._request("core_user_create_users", params, use_post=use_post)

    async def assign_role(self, user_id: int, role: object, context_id: int = 1) -> Dict:
        """Asigna un rol a un usuario en un contexto (default: sistema = 1).
        Acepta role_id numérico o shortname del rol.
        NOTA: No usado actualmente. La asignación de roles se hace via enrol_users()."""
        if isinstance(role, int):
            role_id = role
        else:
            role_id = role_shortname_to_id(str(role))
        return await self._request(
            "core_role_assign_role",
            params={
                "roleid": role_id,
                "userid": user_id,
                "contextid": context_id,
            },
        )

    async def delete_users(self, usernames: List[str]) -> Optional[Dict]:
        """Elimina usuarios resolviendo usernames a IDs numéricos.
        NOTA: No usado actualmente en el flujo ETL."""
        user_ids = await self._get_user_ids_by_usernames(usernames)
        if not user_ids:
            return None
        params = {}
        for i, uid in enumerate(user_ids):
            params[f"userids[{i}]"] = uid
        return await self._request("core_user_delete_users", params)

    async def get_users(self, field: str, values: List[str]) -> List[Dict]:
        """
        Obtiene usuarios según un campo (email, username, etc.).

        Usa core_user_get_users_by_field que soporta múltiples valores.

        Args:
            field: Campo por el que buscar (ej. "email", "username").
            values: Lista de valores a buscar.

        Returns:
            Lista de usuarios encontrados (respuesta directa de Moodle).
        """
        if not values:
            return []
        params: Dict[str, Any] = {"field": field}
        for i, v in enumerate(values):
            params[f"values[{i}]"] = v
        # Usar POST si hay muchos valores para evitar URL too long (>50 valores ≈ >2KB URL)
        return await self._request("core_user_get_users_by_field", params, use_post=len(values) > 50)

    async def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Obtiene un usuario por su username exacto."""
        users = await self.get_users("username", [username])
        return users[0] if users else None

    async def update_users(self, users: List[Dict]) -> List[Dict]:
        """Actualiza usuarios en Moodle vía core_user_update_users.
        Moodle 3.9 requiere id numérico; resuelve username → id si es necesario.
        NOTA: No usado actualmente en el flujo ETL."""
        params = {}
        idx = 0
        for user in users:
            user_id = user.get("id")
            if not user_id and user.get("username"):
                resolved = await self.get_user_by_username(user["username"])
                if resolved:
                    user_id = int(resolved["id"])
            if not user_id:
                logger.warning(f"No se pudo resolver ID para usuario '{user.get('username')}', se omite")
                continue
            params[f"users[{idx}][id]"] = user_id
            if "email" in user:
                params[f"users[{idx}][email]"] = user["email"]
            if "firstname" in user:
                params[f"users[{idx}][firstname]"] = user["firstname"]
            if "lastname" in user:
                params[f"users[{idx}][lastname]"] = user["lastname"]
            idx += 1
        if not params:
            return []
        return await self._request("core_user_update_users", params)

    async def _get_user_ids_by_usernames(self, usernames: List[str]) -> List[int]:
        """
        Convierte una lista de usernames en IDs numéricos (uso interno).
        Necesario para funciones que aún requieren ID (ej. enrol_manual_enrol_users).
        """
        if not usernames:
            return []
        users = await self.get_users("username", usernames)
        return [int(u["id"]) for u in users]

    # ------------------------------------------------------------------
    # Consultas masivas
    # ------------------------------------------------------------------

    async def get_all_users(self, page_size: int = 500) -> List[Dict]:
        """Retorna todos los usuarios de Moodle con paginación.
        core_user_get_users está deprecado desde Moodle 3.8; se usa con
        paginación (limit/offset) para evitar timeouts en sitios grandes."""
        import warnings
        warnings.warn(
            "get_all_users usa core_user_get_users (deprecado desde Moodle 3.8). "
            "Considere migrar a búsquedas específicas con get_users().",
            DeprecationWarning, stacklevel=2,
        )
        all_users: List[Dict] = []
        offset = 0
        while True:
            batch = await self._request(
                "core_user_get_users",
                params={"limit": page_size, "offset": offset},
            )
            if isinstance(batch, dict):
                batch = batch.get("users", [])
            if not batch:
                break
            all_users.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return all_users

    async def get_users_by_role(self, role_shortname: str) -> List[Dict]:
        """Retorna usuarios con un rol específico system-wide (ej. editingteacher)."""
        role_id = role_shortname_to_id(role_shortname)
        assignments = await self._request(
            "core_role_assign_get_role_assignments",
            params={"roleid": role_id},
        )
        user_ids = list({a["userid"] for a in assignments})
        if not user_ids:
            return []
        return await self.get_users("id", [str(uid) for uid in user_ids])

    async def get_courses_by_field(self, field: str, value: str) -> List[Dict]:
        """Busca cursos por campo (shortname, id, idnumber, category)."""
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
    async def enrol_users(self, enrolments: List[Dict], course_map: Dict[str, int] = None, courses: List[Dict] = None) -> Dict[str, Any]:
        """
        Matricula usuarios en cursos con un rol específico.

        Los enrollements deben contener 'username' y 'course_shortname'.
        Internamente se resuelven los IDs necesarios.

        Parámetros:
          - course_map: {shortname: course_id} pre-resuelto (más rápido).
            Si no se provee, se usa courses o se busca via API.
          - courses: lista de dicts de curso. Solo se usa si course_map=None.

        Returns:
            Dict con:
              - success: bool
              - enrolled: int (usuarios matriculados)
              - failed: int (usuarios que no se pudieron resolver)
              - errors: list[str] (detalle de cada fallo)
        """
        missing_username = [e for e in enrolments if "username" not in e]
        if missing_username:
            logger.warning(f"{len(missing_username)} enrolment(s) sin 'username': {missing_username}")
        usernames = [e["username"] for e in enrolments if "username" in e]
        shortnames = [e["course_shortname"] for e in enrolments]

        user_map = {}
        if usernames:
            users_info = await self.get_users("username", usernames)
            user_map = {u["username"]: int(u["id"]) for u in users_info}

        if course_map is None:
            course_map = {}
            if shortnames:
                courses_info = courses if courses else await self.get_courses_by_shortnames(shortnames)
                course_map = {c.get("shortname", ""): int(c["id"]) for c in courses_info if c.get("shortname")}

        params = {}
        idx = 0
        errors: List[str] = []
        for enrol in enrolments:
            user_id = user_map.get(enrol.get("username"))
            course_id = course_map.get(enrol.get("course_shortname"))
            if not user_id or not course_id:
                if not user_id and not course_id:
                    msg = f"Usuario y curso no encontrados: {enrol.get('username')} / {enrol.get('course_shortname')}"
                elif not user_id:
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
                    warnings = r.get("warnings", [])
                    for w in warnings:
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

    # ------------------------------------------------------------------
    # Cierre del cliente
    # ------------------------------------------------------------------
    async def close(self):
        """Cierra el cliente HTTP subyacente."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()