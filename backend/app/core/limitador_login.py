"""
Rate limiting del inicio de sesión (protección contra fuerza bruta).

Cuenta los intentos fallidos por IP + usuario en Redis y bloquea
temporalmente cuando se supera el umbral configurado. El diseño es
*fail-open*: si Redis no está disponible, no se bloquea ningún login
(evita dejar fuera de servicio la autenticación por una caída de Redis).
"""

import logging

import redis.asyncio as aredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class LimitadorLogin:
    """Limitador de intentos de login basado en Redis (contador con TTL)."""

    def __init__(self, max_intentos: int | None = None, ventana_seg: int | None = None):
        self.max_intentos = (
            max_intentos if max_intentos is not None else settings.LOGIN_MAX_ATTEMPTS
        )
        self.ventana_seg = ventana_seg if ventana_seg is not None else settings.LOGIN_WINDOW_SECONDS
        self._pool = None

    async def _redis(self):
        if self._pool is None:
            self._pool = aredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=5,
                socket_timeout=1,
                socket_connect_timeout=1,
            )
        return aredis.Redis(connection_pool=self._pool)

    def _clave(self, ip: str, usuario: str) -> str:
        return f"login_attempts:{ip}:{usuario.lower()}"

    async def esta_bloqueado(self, ip: str, usuario: str) -> bool:
        """Incrementa el contador y devuelve True si el login debe bloquearse.

        El contador se resetea con un TTL en la primera escritura; los
        intentos que superan ``max_intentos`` dentro de la ventana resultan
        bloqueados. Ante cualquier error de Redis, devuelve False (fail-open).
        """
        try:
            r = await self._redis()
            clave = self._clave(ip, usuario)
            intentos = await r.incr(clave)
            if intentos == 1:
                await r.expire(clave, self.ventana_seg)
            return intentos > self.max_intentos
        except Exception:
            logger.warning("Limitador de login no disponible (Redis); fail-open", exc_info=True)
            return False

    async def registrar_exito(self, ip: str, usuario: str) -> None:
        """Limpia el contador de intentos fallidos tras un login exitoso."""
        try:
            r = await self._redis()
            await r.delete(self._clave(ip, usuario))
        except Exception:
            logger.warning("No se pudo limpiar el contador de login (Redis)", exc_info=True)
