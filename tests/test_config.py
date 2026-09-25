import pytest

from app.api.config import ApiSettings
from app.config import get_settings


def test_production_api_requires_authentication() -> None:
    with pytest.raises(ValueError, match="APP_API_KEY"):
        ApiSettings(api_key=None, environment="production")


def test_production_model_settings_fail_closed_when_cache_is_not_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("CACHE_BACKEND", "memory")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="CACHE_BACKEND=redis"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_upstash_backend_requires_both_rest_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("CACHE_BACKEND", "upstash")
    monkeypatch.setenv("CACHE_HMAC_SECRET", "x" * 32)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="UPSTASH_REDIS_REST_URL"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_upstash_backend_uses_rest_environment_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("CACHE_BACKEND", "upstash")
    monkeypatch.setenv("CACHE_HMAC_SECRET", "x" * 32)
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://example.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "test-token")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.cache_backend == "upstash"
        assert settings.upstash_redis_rest_url == "https://example.upstash.io"
        assert settings.upstash_redis_rest_token == "test-token"
    finally:
        get_settings.cache_clear()
