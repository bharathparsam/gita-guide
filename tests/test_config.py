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


def test_guidance_api_requires_explicit_release_or_private_beta_approval() -> None:
    with pytest.raises(ValueError, match="release approval or an explicit private beta"):
        ApiSettings(
            api_key="test",
            guidance_api_enabled=True,
            guidance_release_approved=False,
        )


def test_guidance_api_allows_authenticated_private_beta() -> None:
    settings = ApiSettings(
        api_key="test",
        guidance_api_enabled=True,
        guidance_release_approved=False,
        guidance_private_beta_enabled=True,
    )

    assert settings.guidance_private_beta_enabled is True


def test_private_beta_never_runs_without_api_authentication() -> None:
    with pytest.raises(ValueError, match="APP_API_KEY"):
        ApiSettings(api_key=None, guidance_private_beta_enabled=True)


def test_generation_attempt_budget_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("GENERATION_MAX_ATTEMPTS", "5")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="GENERATION_MAX_ATTEMPTS"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_openrouter_generation_settings_are_independent_from_jev_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_MODEL", "typesafe/jev-1.13")
    monkeypatch.setenv(
        "OPENROUTER_GENERATION_MODEL", "google/gemma-4-31b-it"
    )
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.openrouter_model == "typesafe/jev-1.13"
        assert (
            settings.openrouter_generation_model
            == "google/gemma-4-31b-it"
        )
        assert settings.openrouter_generation_url == "https://openrouter.ai/api/v1"
    finally:
        get_settings.cache_clear()


def test_deepseek_flash_is_the_default_generation_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "development")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.delenv("OPENROUTER_GENERATION_MODEL", raising=False)
    get_settings.cache_clear()
    try:
        assert (
            get_settings().openrouter_generation_model
            == "deepseek/deepseek-v4.1-flash"
        )
    finally:
        get_settings.cache_clear()
