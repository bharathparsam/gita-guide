from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    """Settings owned by the HTTP boundary, independent of model configuration."""

    api_key: str | None
    max_request_body_bytes: int = 16_384
    environment: str = "development"

    def __post_init__(self) -> None:
        if self.max_request_body_bytes <= 0:
            raise ValueError("API_MAX_REQUEST_BODY_BYTES must be greater than zero")
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("Invalid API environment")
        if self.environment == "production" and self.api_key is None:
            raise ValueError("Production requires APP_API_KEY")


def load_api_settings() -> ApiSettings:
    raw_limit = os.getenv("API_MAX_REQUEST_BODY_BYTES", "16384")
    try:
        max_request_body_bytes = int(raw_limit)
    except ValueError as exc:
        raise ValueError("API_MAX_REQUEST_BODY_BYTES must be an integer") from exc

    return ApiSettings(
        api_key=os.getenv("APP_API_KEY", "").strip() or None,
        max_request_body_bytes=max_request_body_bytes,
        environment=os.getenv("APP_ENVIRONMENT", "development").strip().lower(),
    )
