import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.moodle_client import MoodleClient
from app.services.moodle_errors import MoodleAPIError, MoodleOverloadedError


@pytest.fixture
def client():
    with patch("app.services.moodle_client.RedisRateLimiter") as mock_limiter_cls:
        mock_limiter = AsyncMock()
        mock_limiter_cls.return_value = mock_limiter
        c = MoodleClient(token="test-token", base_url="https://moodle.test.com")
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        c._client = mock_http
        yield c, mock_http, mock_limiter


class TestMoodleClientInit:
    def test_requires_token(self):
        with pytest.raises(ValueError, match="token es requerido"):
            MoodleClient(token="", base_url="https://test.com")

    def test_requires_base_url(self):
        with pytest.raises(ValueError, match="base_url es requerido"):
            MoodleClient(token="token", base_url="")


class TestRequest:
    @pytest.mark.asyncio
    async def test_get_success(self, client):
        c, mock_http, _ = client
        expected = {"courses": [{"id": 1, "shortname": "TEST"}]}
        fake_resp = MagicMock()
        fake_resp.json.return_value = expected
        fake_resp.raise_for_status.return_value = None
        mock_http.get.return_value = fake_resp

        result = await c._request("core_course_get_courses", {})
        assert result == expected
        mock_http.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_success(self, client):
        c, mock_http, _ = client
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"success": True}
        fake_resp.raise_for_status.return_value = None
        mock_http.post.return_value = fake_resp

        result = await c._request("core_course_create_courses", {"courses": []}, use_post=True)
        assert result == {"success": True}
        mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_moodle_api_error(self, client):
        c, mock_http, _ = client
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"error": "Invalid param", "errorcode": "invalidparameter"}
        fake_resp.raise_for_status.return_value = None
        mock_http.get.return_value = fake_resp

        with pytest.raises(MoodleAPIError):
            await c._request("core_course_get_courses", {})

    @pytest.mark.asyncio
    async def test_moodle_overloaded(self, client):
        c, mock_http, _ = client
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"error": "Invalid record", "errorcode": "invalidrecord"}
        fake_resp.raise_for_status.return_value = None
        mock_http.get.return_value = fake_resp

        with pytest.raises(MoodleOverloadedError):
            await c._request("core_course_get_courses", {})

    @pytest.mark.asyncio
    async def test_http_503_overloaded(self, client):
        c, mock_http, _ = client
        mock_http.get.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable", request=MagicMock(), response=MagicMock(status_code=503)
        )

        with pytest.raises(MoodleOverloadedError):
            await c._request("core_course_get_courses", {})

    @pytest.mark.asyncio
    async def test_unexpected_response_format(self, client):
        c, mock_http, _ = client
        fake_resp = MagicMock()
        fake_resp.json.return_value = "just a string"
        fake_resp.raise_for_status.return_value = None
        mock_http.get.return_value = fake_resp

        unwrapped = c._request_with_retry.__func__.__wrapped__
        async def _call(*a, **kw):
            return await unwrapped(c, *a, **kw)
        mock_method = AsyncMock(side_effect=_call)
        with patch.object(c, '_request_with_retry', mock_method):
            with pytest.raises(MoodleAPIError, match="Respuesta inesperada"):
                await c._request("core_course_get_courses", {})

    @pytest.mark.asyncio
    async def test_rate_limiter_called(self, client):
        c, mock_http, mock_limiter = client
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"ok": True}
        fake_resp.raise_for_status.return_value = None
        mock_http.get.return_value = fake_resp

        await c._request("core_course_get_courses", {})
        mock_limiter.acquire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close(self, client):
        c, mock_http, _ = client
        await c.close()
        mock_http.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timeout_parameter(self, client):
        c, mock_http, _ = client
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"ok": True}
        fake_resp.raise_for_status.return_value = None
        mock_http.get.return_value = fake_resp

        await c._request("test_ws", {}, timeout=120.0)
        _, kwargs = mock_http.get.call_args
        assert kwargs.get("timeout") == 120.0


class TestGeneratePassword:
    def test_default_length(self):
        from app.services.moodle_client import generate_moodle_password
        pwd = generate_moodle_password()
        assert len(pwd) == 14

    def test_custom_length(self):
        from app.services.moodle_client import generate_moodle_password
        pwd = generate_moodle_password(length=20)
        assert len(pwd) == 20

    def test_contains_required_chars(self):
        from app.services.moodle_client import generate_moodle_password
        pwd = generate_moodle_password()
        assert any(c.islower() for c in pwd)
        assert any(c.isupper() for c in pwd)
        assert any(c.isdigit() for c in pwd)
        assert any(c in "!@#$%&*?" for c in pwd)
