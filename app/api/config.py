from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    """Settings owned by the HTTP boundary, independent of model configuration."""

    api_key: str | None
    max_request_body_bytes: int = 32_768
    environment: str = "development"
    guidance_api_enabled: bool = False
    guidance_release_approved: bool = False
    guidance_private_beta_enabled: bool = False

    def __post_init__(self) -> None:
        if self.max_request_body_bytes <= 0:
            raise ValueError("API_MAX_REQUEST_BODY_BYTES must be greater than zero")
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("Invalid API environment")
        if self.environment == "production" and self.api_key is None:
            raise ValueError("Production requires APP_API_KEY")
        if self.guidance_private_beta_enabled and self.api_key is None:
            raise ValueError("Private beta guidance requires APP_API_KEY")
        if self.guidance_api_enabled and not (
            self.guidance_release_approved or self.guidance_private_beta_enabled
        ):
            raise ValueError(
                "GUIDANCE_API_ENABLED requires release approval or an explicit private beta"
            )


def _as_bool(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def load_api_settings() -> ApiSettings:
    raw_limit = os.getenv("API_MAX_REQUEST_BODY_BYTES", "32768")
    try:
        max_request_body_bytes = int(raw_limit)
    except ValueError as exc:
        raise ValueError("API_MAX_REQUEST_BODY_BYTES must be an integer") from exc

    return ApiSettings(
        api_key=os.getenv("APP_API_KEY", "").strip() or None,
        max_request_body_bytes=max_request_body_bytes,
        environment=os.getenv("APP_ENVIRONMENT", "development").strip().lower(),
        guidance_api_enabled=_as_bool(os.getenv("GUIDANCE_API_ENABLED")),
        guidance_release_approved=_as_bool(os.getenv("GUIDANCE_RELEASE_APPROVED")),
        guidance_private_beta_enabled=_as_bool(
            os.getenv("GUIDANCE_PRIVATE_BETA_ENABLED")
        ),
    )
