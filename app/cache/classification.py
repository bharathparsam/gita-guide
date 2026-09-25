from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from time import time
from typing import Any

from app.cache.backends import CacheBackend
from app.cache.keys import ClassificationCacheKeyContext, HmacCacheKeyBuilder
from app.models.classification import ClassificationResult


@dataclass(frozen=True, slots=True)
class ClassificationCachePolicy:
    ttl_seconds: int = 3600
    minimum_confidence: float = 0.6

    def __post_init__(self) -> None:
        if (
            isinstance(self.ttl_seconds, bool)
            or not isinstance(self.ttl_seconds, int)
            or self.ttl_seconds <= 0
        ):
            raise ValueError("ttl_seconds must be a positive integer")
        if (
            isinstance(self.minimum_confidence, bool)
            or not 0 <= self.minimum_confidence <= 1
        ):
            raise ValueError("minimum_confidence must be between 0 and 1")

    def is_eligible(
        self,
        result: ClassificationResult,
        *,
        scope_threshold: float,
        classification_threshold: float,
    ) -> bool:
        """Low-confidence/review outcomes must always return to the classifier."""
        minimum_confidence = max(
            self.minimum_confidence,
            classification_threshold,
        )
        probability = result.in_scope_probability
        if probability >= scope_threshold:
            scope_certainty = (
                (probability - scope_threshold) / (1 - scope_threshold)
                if scope_threshold < 1
                else 0.0
            )
        else:
            scope_certainty = (
                (scope_threshold - probability) / scope_threshold
                if scope_threshold > 0
                else 0.0
            )
        confidences = (
            scope_certainty,
            result.primary_situation_confidence,
            result.primary_emotion_confidence,
            result.root_conflict_confidence,
        )
        return (
            not result.needs_review
            and not result.low_confidence_fields
            and all(value >= minimum_confidence for value in confidences)
        )


@dataclass(frozen=True, slots=True)
class CachedClassification:
    result: ClassificationResult
    stored_at_epoch_seconds: float


class ClassificationCache:
    """Typed classification cache; exceptions are never accepted as values."""

    def __init__(
        self,
        backend: CacheBackend,
        key_builder: HmacCacheKeyBuilder,
        *,
        policy: ClassificationCachePolicy | None = None,
        clock: Callable[[], float] = time,
    ) -> None:
        self._backend = backend
        self._key_builder = key_builder
        self._policy = policy or ClassificationCachePolicy()
        self._clock = clock

    def key_for(self, message: str, context: ClassificationCacheKeyContext) -> str:
        return self._key_builder.classification_key(message, context)

    def get(
        self,
        message: str,
        context: ClassificationCacheKeyContext,
    ) -> CachedClassification | None:
        key = self.key_for(message, context)
        raw = self._backend.get(key)
        if raw is None:
            return None
        try:
            payload: dict[str, Any] = json.loads(raw)
            result = ClassificationResult.model_validate(payload["result"])
            stored_at = float(payload["stored_at_epoch_seconds"])
        except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            # A bad or old value is a miss. Remove it so subsequent requests heal.
            self._backend.compare_and_delete(key, raw)
            return None
        return CachedClassification(result=result, stored_at_epoch_seconds=stored_at)

    def put(
        self,
        message: str,
        context: ClassificationCacheKeyContext,
        result: ClassificationResult,
    ) -> bool:
        if not self._policy.is_eligible(
            result,
            scope_threshold=context.scope_threshold,
            classification_threshold=context.confidence_threshold,
        ):
            return False
        payload = {
            "stored_at_epoch_seconds": self._clock(),
            "result": result.model_dump(mode="json"),
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        self._backend.set(
            self.key_for(message, context),
            encoded,
            ttl_seconds=self._policy.ttl_seconds,
        )
        return True
