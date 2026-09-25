import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    openrouter_model: str
    openrouter_timeout_seconds: float
    classification_scope_threshold: float
    classification_min_confidence: float
    nvidia_guardrail_url: str | None
    nvidia_guardrail_model: str
    nvidia_guardrail_api_key: str
    nvidia_guardrail_required: bool
    provider_max_attempts: int = 2
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_seconds: float = 30.0
    cache_backend: str = "memory"
    redis_url: str | None = None
    upstash_redis_rest_url: str | None = None
    upstash_redis_rest_token: str | None = None
    cache_hmac_secret: str = ""
    classification_cache_ttl_seconds: int = 3600
    idempotency_ttl_seconds: int = 86400
    cache_tenant_id: str = "default"
    audit_log_path: str | None = "var/audit/phase1.jsonl"
    environment: str = "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = os.getenv("APP_ENVIRONMENT", "development").strip().lower()
    if environment not in {"development", "test", "production"}:
        raise ValueError("APP_ENVIRONMENT must be development, test, or production")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing")

    scope_threshold = float(os.getenv("CLASSIFICATION_SCOPE_THRESHOLD", "0.5"))
    if not 0 <= scope_threshold <= 1:
        raise ValueError("CLASSIFICATION_SCOPE_THRESHOLD must be between 0 and 1")
    min_confidence = float(os.getenv("CLASSIFICATION_MIN_CONFIDENCE", "0.6"))
    if not 0 <= min_confidence <= 1:
        raise ValueError("CLASSIFICATION_MIN_CONFIDENCE must be between 0 and 1")

    timeout = float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "30"))
    if timeout <= 0:
        raise ValueError("OPENROUTER_TIMEOUT_SECONDS must be greater than zero")

    provider_max_attempts = int(os.getenv("PROVIDER_MAX_ATTEMPTS", "2"))
    if provider_max_attempts < 1:
        raise ValueError("PROVIDER_MAX_ATTEMPTS must be at least 1")
    circuit_failure_threshold = int(
        os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
    )
    if circuit_failure_threshold < 1:
        raise ValueError("CIRCUIT_BREAKER_FAILURE_THRESHOLD must be at least 1")
    circuit_recovery_seconds = float(
        os.getenv("CIRCUIT_BREAKER_RECOVERY_SECONDS", "30")
    )
    if circuit_recovery_seconds <= 0:
        raise ValueError("CIRCUIT_BREAKER_RECOVERY_SECONDS must be greater than zero")

    cache_backend = os.getenv("CACHE_BACKEND", "memory").strip().lower()
    if cache_backend not in {"disabled", "memory", "redis", "upstash"}:
        raise ValueError(
            "CACHE_BACKEND must be disabled, memory, redis, or upstash"
        )
    redis_url = os.getenv("REDIS_URL", "").strip() or None
    upstash_redis_rest_url = (
        os.getenv("UPSTASH_REDIS_REST_URL", "").strip() or None
    )
    upstash_redis_rest_token = (
        os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip() or None
    )
    cache_hmac_secret = os.getenv("CACHE_HMAC_SECRET", "")
    if cache_backend == "redis" and not redis_url:
        raise ValueError("REDIS_URL is required when CACHE_BACKEND=redis")
    if cache_backend == "upstash" and (
        not upstash_redis_rest_url or not upstash_redis_rest_token
    ):
        raise ValueError(
            "UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required "
            "when CACHE_BACKEND=upstash"
        )
    if cache_backend in {"redis", "upstash"} and len(
        cache_hmac_secret.encode("utf-8")
    ) < 32:
        raise ValueError(
            "CACHE_HMAC_SECRET must contain at least 32 bytes when shared caching is enabled"
        )
    classification_cache_ttl = int(
        os.getenv("CLASSIFICATION_CACHE_TTL_SECONDS", "3600")
    )
    idempotency_ttl = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))
    if classification_cache_ttl <= 0 or idempotency_ttl <= 0:
        raise ValueError("Cache TTL values must be greater than zero")
    cache_tenant_id = os.getenv("CACHE_TENANT_ID", "default").strip()
    if not cache_tenant_id:
        raise ValueError("CACHE_TENANT_ID cannot be empty")
    audit_log_path = os.getenv("AUDIT_LOG_PATH", "var/audit/phase1.jsonl").strip()
    if environment == "production":
        if cache_backend not in {"redis", "upstash"}:
            raise ValueError("Production requires CACHE_BACKEND=redis or upstash")
        if not audit_log_path:
            raise ValueError("Production requires an AUDIT_LOG_PATH")
        if not _as_bool(os.getenv("NVIDIA_GUARDRAIL_REQUIRED")):
            raise ValueError("Production requires NVIDIA_GUARDRAIL_REQUIRED=true")
        fingerprint_secret = os.getenv("PROMPT_FINGERPRINT_SECRET", "")
        if len(fingerprint_secret.encode("utf-8")) < 32:
            raise ValueError(
                "Production requires PROMPT_FINGERPRINT_SECRET with at least 32 bytes"
            )

    nvidia_api_key = (
        os.getenv("NVIDIA_API_KEY")
        or os.getenv("NVIDIA_GUARDRAIL_API_KEY")
        or ""
    ).strip()
    nvidia_guardrail_url = os.getenv("NVIDIA_GUARDRAIL_URL")
    if not nvidia_guardrail_url and nvidia_api_key:
        nvidia_guardrail_url = "https://integrate.api.nvidia.com/v1"

    return Settings(
        openrouter_api_key=api_key,
        openrouter_model=os.getenv("OPENROUTER_MODEL", "typesafe/jev-1.13"),
        openrouter_timeout_seconds=timeout,
        classification_scope_threshold=scope_threshold,
        classification_min_confidence=min_confidence,
        nvidia_guardrail_url=nvidia_guardrail_url or None,
        nvidia_guardrail_model=os.getenv(
            "NVIDIA_GUARDRAIL_MODEL",
            "nvidia/nemotron-3.5-content-safety",
        ),
        nvidia_guardrail_api_key=nvidia_api_key or "EMPTY",
        nvidia_guardrail_required=_as_bool(os.getenv("NVIDIA_GUARDRAIL_REQUIRED")),
        provider_max_attempts=provider_max_attempts,
        circuit_breaker_failure_threshold=circuit_failure_threshold,
        circuit_breaker_recovery_seconds=circuit_recovery_seconds,
        cache_backend=cache_backend,
        redis_url=redis_url,
        upstash_redis_rest_url=upstash_redis_rest_url,
        upstash_redis_rest_token=upstash_redis_rest_token,
        cache_hmac_secret=cache_hmac_secret,
        classification_cache_ttl_seconds=classification_cache_ttl,
        idempotency_ttl_seconds=idempotency_ttl,
        cache_tenant_id=cache_tenant_id,
        audit_log_path=audit_log_path or None,
        environment=environment,
    )
