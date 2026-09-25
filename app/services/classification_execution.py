from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass

from app.cache import (
    ClassificationCache,
    ClassificationCacheKeyContext,
    IdempotencyStore,
    SingleFlight,
)
from app.cache.keys import normalize_message
from app.models.classification import ClassificationResult


class IdempotencyInProgressError(RuntimeError):
    """Raised when another worker owns the same unfinished idempotent request."""


@dataclass(frozen=True, slots=True)
class ClassificationExecution:
    result: ClassificationResult
    source: str
    cache_age_seconds: float | None = None


class ClassificationExecutor:
    """Run JEV behind exact caching, idempotency, and process-local single flight."""

    def __init__(
        self,
        classifier: Callable[[str], ClassificationResult],
        *,
        cache: ClassificationCache | None = None,
        cache_context: ClassificationCacheKeyContext | None = None,
        idempotency_store: IdempotencyStore | None = None,
        single_flight: SingleFlight | None = None,
    ) -> None:
        if (cache is None) != (cache_context is None):
            raise ValueError("cache and cache_context must be configured together")
        self._classifier = classifier
        self._cache = cache
        self._cache_context = cache_context
        self._idempotency_store = idempotency_store
        self._single_flight = single_flight or SingleFlight()

    def execute(
        self,
        message: str,
        *,
        tenant_id: str,
        idempotency_key: str | None,
    ) -> ClassificationExecution:
        fingerprint: str | None = None
        claim_token: str | None = None

        if idempotency_key and self._idempotency_store is not None:
            fingerprint = self._idempotency_store.fingerprint(
                {
                    "message": normalize_message(message),
                    "cache_context": (
                        asdict(self._cache_context) if self._cache_context else None
                    ),
                }
            )
            claim = self._idempotency_store.claim(
                tenant_id=tenant_id,
                client_key=idempotency_key,
                request_fingerprint=fingerprint,
            )
            if not claim.acquired:
                if claim.record.status == "completed" and claim.record.response is not None:
                    result = ClassificationResult.model_validate(
                        claim.record.response["classification"]
                    )
                    return ClassificationExecution(result=result, source="idempotency")
                raise IdempotencyInProgressError(
                    "an identical idempotent request is still being processed"
                )
            claim_token = claim.record.claim_token

        try:
            execution = self._execute_cached(message)
            if (
                idempotency_key
                and self._idempotency_store is not None
                and fingerprint is not None
                and claim_token is not None
            ):
                self._idempotency_store.complete(
                    tenant_id=tenant_id,
                    client_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    claim_token=claim_token,
                    response={"classification": execution.result.model_dump(mode="json")},
                )
            return execution
        except BaseException:
            if (
                idempotency_key
                and self._idempotency_store is not None
                and fingerprint is not None
                and claim_token is not None
            ):
                self._idempotency_store.abandon(
                    tenant_id=tenant_id,
                    client_key=idempotency_key,
                    request_fingerprint=fingerprint,
                    claim_token=claim_token,
                )
            raise

    def _execute_cached(self, message: str) -> ClassificationExecution:
        if self._cache is None or self._cache_context is None:
            return ClassificationExecution(
                result=self._classifier(message),
                source="provider",
            )

        cached = self._cache.get(message, self._cache_context)
        if cached is not None:
            return ClassificationExecution(
                result=cached.result,
                source="cache",
                cache_age_seconds=self._cache_age(cached.stored_at_epoch_seconds),
            )

        cache_key = self._cache.key_for(message, self._cache_context)

        def classify_once() -> ClassificationExecution:
            second_lookup = self._cache.get(message, self._cache_context)
            if second_lookup is not None:
                return ClassificationExecution(
                    result=second_lookup.result,
                    source="cache",
                    cache_age_seconds=self._cache_age(
                        second_lookup.stored_at_epoch_seconds
                    ),
                )
            result = self._classifier(message)
            self._cache.put(message, self._cache_context, result)
            return ClassificationExecution(result=result, source="provider")

        flight = self._single_flight.do(cache_key, classify_once)
        if flight.shared and flight.value.source == "provider":
            return ClassificationExecution(result=flight.value.result, source="coalesced")
        return flight.value

    @staticmethod
    def _cache_age(stored_at_epoch_seconds: float) -> float | None:
        # Wall-clock age is useful operational metadata only. Avoid returning a
        # negative age if hosts experience a small clock correction.
        from time import time

        return max(0.0, time() - stored_at_epoch_seconds)
