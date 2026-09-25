from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import time
from typing import Any

from app.cache.backends import CacheBackend
from app.cache.keys import HmacCacheKeyBuilder, RetrievalCacheKeyContext


@dataclass(frozen=True, slots=True)
class CachedRetrievalItem:
    chunk_id: str
    similarity_score: float
    rerank_score: float
    dense_rank: int
    final_rank: int
    validation_probability: float


@dataclass(frozen=True, slots=True)
class CachedRetrieval:
    items: tuple[CachedRetrievalItem, ...]
    candidate_count: int
    stored_at_epoch_seconds: float
    validation_rejected_count: int
    validation_model: str
    validation_provider_request_id: str | None


class RetrievalCache:
    """Stores ranked references; verse text remains in the bundled corpus."""

    def __init__(
        self,
        backend: CacheBackend,
        key_builder: HmacCacheKeyBuilder,
        *,
        ttl_seconds: int = 21_600,
        clock: Callable[[], float] = time,
    ) -> None:
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be a positive integer")
        self._backend = backend
        self._key_builder = key_builder
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def key_for(self, query: str, context: RetrievalCacheKeyContext) -> str:
        return self._key_builder.retrieval_key(query, context)

    def get(self, query: str, context: RetrievalCacheKeyContext) -> CachedRetrieval | None:
        key = self.key_for(query, context)
        raw = self._backend.get(key)
        if raw is None:
            return None
        try:
            payload: dict[str, Any] = json.loads(raw)
            items = tuple(
                CachedRetrievalItem(
                    chunk_id=str(item["chunk_id"]),
                    similarity_score=float(item["similarity_score"]),
                    rerank_score=float(item["rerank_score"]),
                    dense_rank=int(item["dense_rank"]),
                    final_rank=int(item["final_rank"]),
                    validation_probability=float(item["validation_probability"]),
                )
                for item in payload["items"]
            )
            candidate_count = int(payload["candidate_count"])
            stored_at = float(payload["stored_at_epoch_seconds"])
            validation_rejected_count = int(payload["validation_rejected_count"])
            validation_model = str(payload["validation_model"])
            raw_provider_request_id = payload.get("validation_provider_request_id")
            validation_provider_request_id = (
                str(raw_provider_request_id)
                if raw_provider_request_id is not None
                else None
            )
            if not 1 <= len(items) <= context.top_k:
                raise ValueError("invalid cached result size")
            if candidate_count < len(items):
                raise ValueError("invalid cached candidate count")
            if tuple(item.final_rank for item in items) != tuple(range(1, len(items) + 1)):
                raise ValueError("invalid cached ranks")
            if any(
                not item.chunk_id
                or not math.isfinite(item.similarity_score)
                or not -1 <= item.similarity_score <= 1
                or not math.isfinite(item.rerank_score)
                or item.dense_rank < 1
                or not 0 <= item.validation_probability <= 1
                for item in items
            ):
                raise ValueError("invalid cached retrieval item")
            if validation_rejected_count < 0 or not validation_model:
                raise ValueError("invalid cached validation metadata")
        except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            self._backend.compare_and_delete(key, raw)
            return None
        return CachedRetrieval(
            items=items,
            candidate_count=candidate_count,
            stored_at_epoch_seconds=stored_at,
            validation_rejected_count=validation_rejected_count,
            validation_model=validation_model,
            validation_provider_request_id=validation_provider_request_id,
        )

    def put(
        self,
        query: str,
        context: RetrievalCacheKeyContext,
        items: Sequence[CachedRetrievalItem],
        *,
        candidate_count: int,
        validation_rejected_count: int,
        validation_model: str,
        validation_provider_request_id: str | None,
    ) -> bool:
        if not items:
            return False
        if len(items) > context.top_k:
            raise ValueError("retrieval cache value exceeds configured top_k")
        if candidate_count < len(items):
            raise ValueError("candidate_count cannot be smaller than cached items")
        if validation_rejected_count < 0 or not validation_model.strip():
            raise ValueError("invalid retrieval validation metadata")
        payload = {
            "stored_at_epoch_seconds": self._clock(),
            "candidate_count": candidate_count,
            "validation_rejected_count": validation_rejected_count,
            "validation_model": validation_model,
            "validation_provider_request_id": validation_provider_request_id,
            "items": [
                {
                    "chunk_id": item.chunk_id,
                    "similarity_score": item.similarity_score,
                    "rerank_score": item.rerank_score,
                    "dense_rank": item.dense_rank,
                    "final_rank": item.final_rank,
                    "validation_probability": item.validation_probability,
                }
                for item in items
            ],
        }
        self._backend.set(
            self.key_for(query, context),
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
            ttl_seconds=self._ttl_seconds,
        )
        return True

    def delete(self, query: str, context: RetrievalCacheKeyContext) -> bool:
        return self._backend.delete(self.key_for(query, context))
