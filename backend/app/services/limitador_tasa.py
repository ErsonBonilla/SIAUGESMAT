"""
Rate Limiter basado en el algoritmo Token Bucket.

Ofrece dos implementaciones:
  - TokenBucket / RateLimiter: local (en memoria) para un solo worker.
  - RedisRateLimiter: distribuido vía Redis para coordinar entre workers.
"""

import asyncio
import logging
import secrets
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token Bucket local (en memoria)
# ---------------------------------------------------------------------------


class CubetaTokens:
    def __init__(self, rate: float, burst: int):
        if rate <= 0:
            raise ValueError("La tasa (rate) debe ser positiva")
        if burst <= 0:
            raise ValueError("La capacidad (burst) debe ser positiva")
        self.velocidad = rate
        self.rafaga = burst
        self.fichas = float(burst)
        self.ultima_actualizacion = time.monotonic()

    async def consumir(self, tokens: int = 1) -> None:
        if tokens > self.rafaga:
            raise ValueError(f"No se pueden consumir {tokens} tokens, máximo {self.rafaga}")
        while True:
            now = time.monotonic()
            elapsed = now - self.ultima_actualizacion
            self.fichas = min(self.rafaga, self.fichas + elapsed * self.velocidad)
            self.ultima_actualizacion = now
            if self.fichas >= tokens:
                self.fichas -= tokens
                return
            wait = (tokens - self.fichas) / self.velocidad
            await asyncio.sleep(wait + 0.001)


class LimitadorTasa:
    def __init__(self, rate: float, burst: int):
        self.cubeta = CubetaTokens(rate, burst)

    async def adquirir(self) -> None:
        await self.cubeta.consumir()

        # ---------------------------------------------------------------------------
        # Redis Rate Limiter (distribuido, sliding-window via sorted sets)
        # ---------------------------------------------------------------------------


class LimitadorTasaRedis:
    """Rate limiter distribuido vía Redis.
    Usa sorted set con timestamps como scores para ventana deslizante.
    Todos los workers que comparten el mismo Redis coordinan el límite."""

    def __init__(self, rate: float = 5, window: int = 1):
        self.velocidad = rate
        self.ventana = window
        self._grupo_conexiones = None
        self._redis = None

    async def _obtener_grupo_conexiones(self):
        if self._grupo_conexiones is None:
            import redis.asyncio as aredis

            self._grupo_conexiones = aredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=5,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        return self._grupo_conexiones

    async def adquirir(self) -> None:
        import redis.asyncio as aredis

        pool = await self._obtener_grupo_conexiones()
        if self._redis is None:
            self._redis = aredis.Redis(connection_pool=pool)
        key = "ratelimit:moodle"
        now = time.monotonic()
        window_start = now - self.ventana
        pipe = self._redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now) + str(secrets.randbits(16)): now})
        pipe.zcard(key)
        pipe.expire(key, self.ventana + 1)
        _, _, count, _ = await pipe.execute()
        if count > self.velocidad:
            wait = (count - self.velocidad) * (self.ventana / self.velocidad)
            await asyncio.sleep(wait)

    async def close(self):
        if self._grupo_conexiones is not None:
            await self._grupo_conexiones.disconnect()
            self._grupo_conexiones = None
