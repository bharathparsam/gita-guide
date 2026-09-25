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


@dataclass(frozen=True, slots=True)
class RetrievalCacheKeyContext:
    """Every version and policy input capable of changing retrieved chunks."""

    tenant_id: str
    embedding_model: str
    corpus_sha256: str
    pipeline_version: str
    reranker_version: str
    validator_model: str
    validator_prompt_version: str
    validator_threshold: float
    candidate_k: int
    top_k: int
    minimum_score: float
    mmr_lambda: float
    max_per_chapter: int
    allowed_source_ids: tuple[str, ...]
    allowed_speakers: tuple[str, ...]
    key_version: str = "v1"

    def __post_init__(self) -> None:
        for name in (
            "tenant_id",
            "embedding_model",
            "corpus_sha256",
            "pipeline_version",
            "reranker_version",
            "validator_model",
            "validator_prompt_version",
            "key_version",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be empty")
        if self.candidate_k < 1 or self.top_k < 1 or self.top_k > 5:
            raise ValueError("candidate_k and top_k must be positive and top_k cannot exceed 5")
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be at least top_k")
        if not -1 <= self.minimum_score <= 1:
            raise ValueError("minimum_score must be between -1 and 1")
        if not 0 <= self.mmr_lambda <= 1:
            raise ValueError("mmr_lambda must be between 0 and 1")
        if not 0 <= self.validator_threshold <= 1:
            raise ValueError("validator_threshold must be between 0 and 1")
        if self.max_per_chapter < 1:
            raise ValueError("max_per_chapter must be at least 1")
        if not self.allowed_source_ids or not self.allowed_speakers:
            raise ValueError("retrieval source and speaker allowlists cannot be empty")


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

    def retrieval_key(self, query: str, context: RetrievalCacheKeyContext) -> str:
        payload = {
            "context": asdict(context),
            "query": normalize_message(query),
        }
        return f"retrieval:{context.key_version}:{self._digest(payload)}"

    def idempotency_key(self, *, tenant_id: str, client_key: str) -> str:
        if not tenant_id.strip() or not client_key.strip():
            raise ValueError("tenant_id and client_key cannot be empty")
        return f"idempotency:v1:{self._digest({'tenant_id': tenant_id, 'key': client_key})}"

    def request_fingerprint(self, payload: Any) -> str:
        return f"request:v1:{self._digest(payload)}"
