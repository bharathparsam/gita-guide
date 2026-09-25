from __future__ import annotations

import json
import logging
import os
import secrets
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.observability.fingerprint import PromptFingerprinter


LOGGER_NAME = "gita_guide"
_STANDARD_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)
_request_id: ContextVar[str | None] = ContextVar("gita_guide_request_id", default=None)
_ephemeral_fingerprint_secret = secrets.token_bytes(32)


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def prompt_content_logging_enabled() -> bool:
    """Return whether raw prompts may be copied into application logs."""
    return _as_bool(os.getenv("LOG_PROMPT_CONTENT"), default=False)


def _prompt_fingerprinter() -> PromptFingerprinter:
    configured_secret = os.getenv("PROMPT_FINGERPRINT_SECRET", "")
    secret = (
        configured_secret.encode("utf-8")
        if configured_secret
        else _ephemeral_fingerprint_secret
    )
    key_id = os.getenv(
        "PROMPT_FINGERPRINT_KEY_ID",
        "configured-v1" if configured_secret else "ephemeral-process-v1",
    )
    return PromptFingerprinter(secret, key_id=key_id)


class JsonFormatter(logging.Formatter):
    """Small JSON formatter with stable fields for log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_FIELDS and not key.startswith("_"):
                payload[key] = value
        contextual_request_id = current_request_id()
        if contextual_request_id is not None and "request_id" not in payload:
            payload["request_id"] = contextual_request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str | None = None) -> None:
    """Configure application JSON logs once, writing to stderr."""
    logger = logging.getLogger(LOGGER_NAME)
    resolved_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logger.setLevel(resolved_level)
    logger.propagate = False

    if any(getattr(handler, "_gita_guide_handler", False) for handler in logger.handlers):
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    handler._gita_guide_handler = True  # type: ignore[attr-defined]
    logger.addHandler(handler)


def get_logger(component: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{component}")


def current_request_id() -> str | None:
    return _request_id.get()


@contextmanager
def request_logging_context(request_id: str) -> Iterator[None]:
    token = _request_id.set(request_id)
    try:
        yield
    finally:
        _request_id.reset(token)


def prompt_log_fields(prompt: Any, *, include_content: bool | None = None) -> dict[str, Any]:
    """Create searchable prompt metadata without exposing content by default."""
    if isinstance(prompt, str):
        canonical = prompt
    else:
        canonical = json.dumps(prompt, default=str, sort_keys=True, separators=(",", ":"))

    fields: dict[str, Any] = _prompt_fingerprinter().fingerprint(canonical).as_log_fields()
    if include_content if include_content is not None else prompt_content_logging_enabled():
        fields["prompt"] = prompt
    return fields
