"""
Rate Limiter basado en el algoritmo Token Bucket.

Controla la frecuencia de llamadas a servicios externos (Moodle)
para no superar los límites configurados, utilizando un diseño
asíncrono compatible con los clientes HTTP de httpx.
"""

import asyncio
import time


class TokenBucket:
    """
    Implementación de un cubo de tokens (token bucket) para limitar
    el ritmo de ejecución de operaciones.

    Permite ráfagas (burst) hasta un máximo de tokens y luego regula
    la velocidad de adquisición según la tasa configurada.
    """

    def __init__(self, rate: float, burst: int):
        """
        Args:
            rate: Número de tokens generados por segundo.
            burst: Cantidad máxima de tokens que puede almacenar el cubo.
        """
        if rate <= 0:
            raise ValueError("La tasa (rate) debe ser positiva")
        if burst <= 0:
            raise ValueError("La capacidad (burst) debe ser positiva")

        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()

    async def consume(self, tokens: int = 1) -> None:
        """
        Espera hasta que haya suficientes tokens disponibles y los consume.

        Args:
            tokens: Cantidad de tokens a consumir (por defecto 1).
        """
        if tokens > self.burst:
            # No se puede consumir más tokens de los que el cubo puede almacenar
            raise ValueError(f"No se pueden consumir {tokens} tokens, máximo {self.burst}")

        while True:
            now = time.monotonic()
            elapsed = now - self.last_update
            # Añadir tokens generados en el tiempo transcurrido
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return

            # Calcular tiempo de espera necesario para reunir los tokens que faltan
            wait = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait + 0.001)  # Pequeña fracción extra para estabilidad


class RateLimiter:
    """
    Envoltorio simple de TokenBucket para control de concurrencia.

    Se utiliza como un semáforo asíncrono: cada petición a Moodle debe
    llamar a acquire() antes de ejecutarse.
    """

    def __init__(self, rate: float, burst: int):
        self.bucket = TokenBucket(rate, burst)

    async def acquire(self) -> None:
        """Bloquea hasta que se permita una nueva operación."""
        await self.bucket.consume()