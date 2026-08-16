import logging
import secrets
import time
from typing import Any

import httpx
from tenacity import before_log, retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.errores_moodle import (
    ErrorApiMoodle,
    ErrorMoodleSobrecargado,
    _es_error_reintentable,
    es_moodle_sobrecargado,
)
from app.services.limitador_tasa import LimitadorTasaRedis

logger = logging.getLogger(__name__)


def generar_password_moodle(length: int = 14) -> str:
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


class ClienteMoodle:
    """Cliente HTTP base para la API REST de Moodle con rate limiting y reintentos."""

    def __init__(self, token: str, base_url: str, version: str | None = None):
        if not token:
            raise ValueError("token es requerido para MoodleClient")
        if not base_url:
            raise ValueError("base_url es requerido para MoodleClient")
        self._token = token
        self._url_base = base_url.rstrip("/") + "/webservice/rest/server.php"
        if settings.REDIS_URL:
            self._limitador_tasa = LimitadorTasaRedis(
                rate=settings.MOODLE_MAX_REQUESTS_PER_SECOND,
                window=1,
            )
        else:
            from app.services.limitador_tasa import LimitadorTasa

            self._limitador_tasa = LimitadorTasa(
                rate=settings.MOODLE_MAX_REQUESTS_PER_SECOND,
                burst=settings.MOODLE_BURST_SIZE,
            )
        self._cliente = httpx.AsyncClient(timeout=settings.MOODLE_REQUEST_TIMEOUT)

    async def _solicitar(
        self,
        wsfunction: str,
        params: dict[str, Any],
        use_post: bool = False,
        timeout: float | None = None,
    ) -> Any:
        _t0 = time.monotonic()
        await self._limitador_tasa.adquirir()
        return await self._solicitar_con_reintento(wsfunction, params, use_post, timeout, _t0)

    @retry(
        retry=retry_if_exception(_es_error_reintentable),
        stop=stop_after_attempt(settings.MOODLE_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _solicitar_con_reintento(
        self,
        wsfunction: str,
        params: dict[str, Any],
        use_post: bool,
        timeout: float | None,
        _t0: float,
    ) -> Any:
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
                response = await self._cliente.post(
                    self._url_base, data={**payload, **params}, **request_kwargs
                )
            else:
                response = await self._cliente.get(
                    self._url_base, params={**payload, **params}, **request_kwargs
                )
            response.raise_for_status()
        except Exception as e:
            if es_moodle_sobrecargado(e):
                raise ErrorMoodleSobrecargado(str(e)[:200]) from e
            raise

        data = response.json()
        _duration = (time.monotonic() - _t0) * 1000

        if data is not None and not isinstance(data, (dict, list)):
            raise ErrorApiMoodle(f"Respuesta inesperada de {wsfunction}: {str(data)[:300]}")

        if isinstance(data, dict) and ("error" in data or "exception" in data):
            error_code = data.get("errorcode", "")
            error_msg = data.get("error") or data.get("exception") or data.get("message", "")
            logger.error(f"Moodle API error [{wsfunction}]: {error_code} — {error_msg}")
            exc = ErrorApiMoodle(
                data.get("error") or data.get("exception"),
                data.get("errorcode"),
            )
            if es_moodle_sobrecargado(exc):
                raise ErrorMoodleSobrecargado(str(exc)[:200]) from exc
            raise exc

        return data

    async def close(self):
        await self._cliente.aclose()
        cerrar_limitador = getattr(self._limitador_tasa, "close", None)
        if cerrar_limitador is not None:
            await cerrar_limitador()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
