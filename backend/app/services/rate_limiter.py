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

class TokenBucket:
    def __init__(self, rate: float, burst: int):
        if rate <= 0:
            raise ValueError("La tasa (rate) debe ser positiva")
        if burst <= 0:
            raise ValueError("La capacidad (burst) debe ser positiva")
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()

    async def consume(self, tokens: int = 1) -> None:
        if tokens > self.burst:
            raise ValueError(f"No se pueden consumir {tokens} tokens, máximo {self.burst}")
        while True:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return
            wait = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait + 0.001)


class RateLimiter:
    def __init__(self, rate: float, burst: int):
        self.bucket = TokenBucket(rate, burst)

    async def acquire(self) -> None:
        await self.bucket.consume()


# ---------------------------------------------------------------------------
# Redis Rate Limiter (distribuido, sliding-window via sorted sets)
# ---------------------------------------------------------------------------

class RedisRateLimiter:
    """Rate limiter distribuido vía Redis.
    Usa sorted set con timestamps como scores para ventana deslizante.
    Todos los workers que comparten el mismo Redis coordinan el límite."""

    def __init__(self, rate: float = 5, window: int = 1):
        self.rate = rate
        self.window = window
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import redis.asyncio as aredis
            self._pool = aredis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=5,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
        return self._pool

    async def acquire(self) -> None:
        import redis.asyncio as aredis
        pool = await self._get_pool()
        r = aredis.Redis(connection_pool=pool)
        key = "ratelimit:moodle"
        now = time.monotonic()
        window_start = now - self.window
        try:
            pipe = r.pipeline(transaction=True)
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now) + str(secrets.randbits(16)): now})
            pipe.zcard(key)
            pipe.expire(key, self.window + 1)
            _, _, count, _ = await pipe.execute()
            if count > self.rate:
                await asyncio.sleep((count - self.rate) * (self.window / self.rate))
        finally:
            await r.aclose()
