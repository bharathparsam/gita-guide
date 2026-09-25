from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


_WHITESPACE = re.compile(r"\s+")


def normalize_message(message: str) -> str:
    """Canonicalize transport-only differences while preserving message meaning."""
    if not isinstance(message, str):
        raise TypeError("message must be a string")
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", message).strip())


@dataclass(frozen=True, slots=True)
class ClassificationCacheKeyContext:
    """Every input capable of changing a classification decision."""

    tenant_id: str
    model_version: str
    taxonomy_version: str
    prompt_version: str
    confidence_threshold: float
    scope_threshold: float
    result_schema_version: str = "1.0"
    key_version: str = "v1"

    def __post_init__(self) -> None:
        for name in (
            "tenant_id",
            "model_version",
            "taxonomy_version",
            "prompt_version",
            "result_schema_version",
            "key_version",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be empty")
        for name in ("confidence_threshold", "scope_threshold"):
            value = getattr(self, name)
            if isinstance(value, bool) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


class HmacCacheKeyBuilder:
    """Creates opaque, deterministic keys without exposing sensitive input text."""

    def __init__(self, secret: str | bytes) -> None:
        encoded = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
        if len(encoded) < 32:
            raise ValueError("cache HMAC secret must contain at least 32 bytes")
        self._secret = encoded

    def _digest(self, payload: Any) -> str:
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hmac.new(self._secret, canonical, hashlib.sha256).hexdigest()

    def classification_key(
        self,
        message: str,
        context: ClassificationCacheKeyContext,
    ) -> str:
        payload = {
            "context": asdict(context),
            "message": normalize_message(message),
        }
        return f"classification:{context.key_version}:{self._digest(payload)}"

    def idempotency_key(self, *, tenant_id: str, client_key: str) -> str:
        if not tenant_id.strip() or not client_key.strip():
            raise ValueError("tenant_id and client_key cannot be empty")
        return f"idempotency:v1:{self._digest({'tenant_id': tenant_id, 'key': client_key})}"

    def request_fingerprint(self, payload: Any) -> str:
        return f"request:v1:{self._digest(payload)}"
