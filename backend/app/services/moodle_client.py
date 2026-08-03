import logging
import secrets
import time
from typing import Any

import httpx
from tenacity import before_log, retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.moodle_errors import (
    MoodleAPIError,
    MoodleOverloadedError,
    _is_retryable_error,
    is_moodle_overloaded,
)
from app.services.rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)


def generate_moodle_password(length: int = 14) -> str:
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


class MoodleClient:
    """Cliente HTTP base para la API REST de Moodle con rate limiting y reintentos."""

    def __init__(self, token: str, base_url: str, version: str | None = None):
        if not token:
            raise ValueError("token es requerido para MoodleClient")
        if not base_url:
            raise ValueError("base_url es requerido para MoodleClient")
        self._token = token
        self._base_url = base_url.rstrip("/") + "/webservice/rest/server.php"
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

    async def _request(self, wsfunction: str, params: dict[str, Any], use_post: bool = False,
                       timeout: float | None = None) -> Any:
        _t0 = time.monotonic()
        await self._rate_limiter.acquire()
        return await self._request_with_retry(wsfunction, params, use_post, timeout, _t0)

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        stop=stop_after_attempt(settings.MOODLE_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before=before_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _request_with_retry(self, wsfunction: str, params: dict[str, Any],
                                   use_post: bool, timeout: float | None,
                                   _t0: float) -> Any:
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
        _duration = (time.monotonic() - _t0) * 1000

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

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
