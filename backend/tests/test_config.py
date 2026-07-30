import pytest

from app.core.config import Settings


class TestSettings:
    def test_default_values(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET_KEY="test-secret",
            MOODLE_URL="https://moodle.test.com",
            MOODLE_TOKEN="test-token",
        )
        assert s.PROJECT_NAME == "SIAUGESMAT"
        assert s.MOODLE_URL == "https://moodle.test.com"
        assert s.MOODLE_MAX_REQUESTS_PER_SECOND == 5

    def test_get_moodle_config_presencial(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET_KEY="test-secret",
            MOODLE_URL="https://presencial.test.com",
            MOODLE_TOKEN="presencial-token",
            MOODLE_URL__PRESENCIAL="https://presencial.moodle.com",
            MOODLE_TOKEN__PRESENCIAL="token-presencial",
            MOODLE_VERSION__PRESENCIAL="4.0",
        )
        cfg = s.get_moodle_config("PRESENCIAL")
        assert cfg["url"] == "https://presencial.moodle.com"
        assert cfg["token"] == "token-presencial"
        assert cfg["version"] == "4.0"

    def test_get_moodle_config_distancia(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET_KEY="test-secret",
            MOODLE_URL="https://distancia.test.com",
            MOODLE_TOKEN="distancia-token",
            MOODLE_URL__DISTANCIA="https://distancia.moodle.com",
            MOODLE_TOKEN__DISTANCIA="token-distancia",
            MOODLE_VERSION__DISTANCIA="3.11",
        )
        cfg = s.get_moodle_config("distancia")
        assert cfg["url"] == "https://distancia.moodle.com"
        assert cfg["token"] == "token-distancia"
        assert cfg["version"] == "3.11"

    def test_get_moodle_config_fallback(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET_KEY="test-secret",
            MOODLE_URL="https://base.moodle.com",
            MOODLE_TOKEN="base-token",
            MOODLE_VERSION="3.9",
            MOODLE_URL__PRESENCIAL="",
            MOODLE_TOKEN__PRESENCIAL="",
            MOODLE_VERSION__PRESENCIAL="",
        )
        cfg = s.get_moodle_config("PRESENCIAL")
        assert cfg["url"] == "https://base.moodle.com"
        assert cfg["token"] == "base-token"
        assert cfg["version"] == "3.9"

    def test_get_moodle_config_raises_on_missing(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET_KEY="test-secret",
            MOODLE_URL="",
            MOODLE_TOKEN="",
            MOODLE_ADMIN_TOKEN="",
            MOODLE_VERSION="",
            MOODLE_URL__PRESENCIAL="",
            MOODLE_TOKEN__PRESENCIAL="",
            MOODLE_VERSION__PRESENCIAL="",
        )
        with pytest.raises(ValueError, match="Ninguna variable configurada"):
            s.get_moodle_config("PRESENCIAL")

    def test_validate_critical_all_ok(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET_KEY="test-secret",
        )
        s.validate_critical()

    def test_validate_critical_missing_db(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET_KEY="test-secret",
        )
        with pytest.raises(ValueError, match="DATABASE_URL"):
            s.validate_critical()

    def test_validate_critical_missing_redis(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="",
            JWT_SECRET_KEY="test-secret",
        )
        with pytest.raises(ValueError, match="REDIS_URL"):
            s.validate_critical()

    def test_validate_critical_missing_jwt(self):
        s = Settings(
            _env_file=None,
            DATABASE_URL="sqlite:///test.db",
            REDIS_URL="redis://localhost:6379/0",
            JWT_SECRET_KEY="",
        )
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            s.validate_critical()
