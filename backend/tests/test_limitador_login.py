"""
Pruebas unitarias del limitador de intentos de login (H1).

El limitador es fail-open: ante cualquier error de Redis no bloquea el login.
Aquí se mockea redis.asyncio para verificar la lógica del contador sin Redis.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.limitador_login import LimitadorLogin


@pytest.fixture
def mock_redis():
    with patch("app.core.limitador_login.aredis") as mock_aredis:
        conn = AsyncMock()
        mock_aredis.ConnectionPool.from_url.return_value = object()
        mock_aredis.Redis.return_value = conn
        yield conn


@pytest.mark.asyncio
async def test_no_bloquea_dentro_del_umbral(mock_redis):
    lim = LimitadorLogin(max_intentos=5, ventana_seg=300)
    mock_redis.incr.return_value = 1

    bloqueado = await lim.esta_bloqueado("1.2.3.4", "profesor")

    assert bloqueado is False
    mock_redis.expire.assert_awaited_once()


@pytest.mark.asyncio
async def test_bloquea_al_superar_umbral(mock_redis):
    lim = LimitadorLogin(max_intentos=5, ventana_seg=300)
    mock_redis.incr.return_value = 6

    bloqueado = await lim.esta_bloqueado("1.2.3.4", "profesor")

    assert bloqueado is True


@pytest.mark.asyncio
async def test_fail_open_ante_error_de_redis():
    lim = LimitadorLogin(max_intentos=5, ventana_seg=300)
    with patch("app.core.limitador_login.aredis") as mock_aredis:
        mock_aredis.ConnectionPool.from_url.side_effect = ConnectionError("sin redis")

        bloqueado = await lim.esta_bloqueado("1.2.3.4", "profesor")

    assert bloqueado is False


@pytest.mark.asyncio
async def test_registrar_exito_borra_contador(mock_redis):
    lim = LimitadorLogin(max_intentos=5, ventana_seg=300)

    await lim.registrar_exito("1.2.3.4", "profesor")

    mock_redis.delete.assert_awaited_once()
