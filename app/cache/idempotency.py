from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from time import time
from typing import Any, Literal
from uuid import uuid4

from app.cache.backends import CacheBackend
from app.cache.keys import HmacCacheKeyBuilder


IdempotencyStatus = Literal["in_progress", "completed"]


class IdempotencyConflict(RuntimeError):
    """Raised when a client reuses a key for a different request payload."""


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    request_fingerprint: str
    claim_token: str
    status: IdempotencyStatus
    created_at_epoch_seconds: float
    response: dict[str, Any] | None = None
    completed_at_epoch_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    acquired: bool
    record: IdempotencyRecord


class IdempotencyStore:
    """Atomic claim store for safe retries.

    Failed operations call :meth:`abandon`; errors are deliberately never cached.
    """

    def __init__(
        self,
        backend: CacheBackend,
        key_builder: HmacCacheKeyBuilder,
        *,
        ttl_seconds: int = 86_400,
        clock: Callable[[], float] = time,
    ) -> None:
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, int)
            or ttl_seconds <= 0
        ):
            raise ValueError("ttl_seconds must be a positive integer")
        self._backend = backend
        self._key_builder = key_builder
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def fingerprint(self, payload: Any) -> str:
        """Create a privacy-preserving fingerprint for conflict detection."""
        return self._key_builder.request_fingerprint(payload)

    def _key(self, tenant_id: str, client_key: str) -> str:
        return self._key_builder.idempotency_key(
            tenant_id=tenant_id,
            client_key=client_key,
        )

    @staticmethod
    def _encode(record: IdempotencyRecord) -> bytes:
        return json.dumps(asdict(record), separators=(",", ":"), sort_keys=True).encode()

    @staticmethod
    def _decode(raw: bytes) -> IdempotencyRecord:
        payload = json.loads(raw)
        record = IdempotencyRecord(**payload)
        if record.status not in ("in_progress", "completed"):
            raise ValueError("invalid idempotency status")
        if not record.request_fingerprint or not record.claim_token:
            raise ValueError("invalid idempotency record identity")
        if record.status == "completed" and record.response is None:
            raise ValueError("completed idempotency record has no response")
        return record

    @staticmethod
    def _verify_fingerprint(record: IdempotencyRecord, fingerprint: str) -> None:
        if record.request_fingerprint != fingerprint:
            raise IdempotencyConflict(
                "idempotency key was already used for a different request"
            )

    def get(self, *, tenant_id: str, client_key: str) -> IdempotencyRecord | None:
        raw = self._backend.get(self._key(tenant_id, client_key))
        if raw is None:
            return None
        try:
            return self._decode(raw)
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            self._backend.compare_and_delete(self._key(tenant_id, client_key), raw)
            return None

    def claim(
        self,
        *,
        tenant_id: str,
        client_key: str,
        request_fingerprint: str,
    ) -> IdempotencyClaim:
        record = IdempotencyRecord(
            request_fingerprint=request_fingerprint,
            claim_token=str(uuid4()),
            status="in_progress",
            created_at_epoch_seconds=self._clock(),
        )
        key = self._key(tenant_id, client_key)
        if self._backend.set_if_absent(
            key,
            self._encode(record),
            ttl_seconds=self._ttl_seconds,
        ):
            return IdempotencyClaim(acquired=True, record=record)

        existing = self.get(tenant_id=tenant_id, client_key=client_key)
        # The entry may expire between SET NX and GET; one bounded retry is enough.
        if existing is None and self._backend.set_if_absent(
            key,
            self._encode(record),
            ttl_seconds=self._ttl_seconds,
        ):
            return IdempotencyClaim(acquired=True, record=record)
        if existing is None:
            existing = self.get(tenant_id=tenant_id, client_key=client_key)
        if existing is None:
            raise RuntimeError("idempotency record changed during claim")
        self._verify_fingerprint(existing, request_fingerprint)
        return IdempotencyClaim(acquired=False, record=existing)

    def complete(
        self,
        *,
        tenant_id: str,
        client_key: str,
        request_fingerprint: str,
        claim_token: str,
        response: Mapping[str, Any],
    ) -> IdempotencyRecord:
        existing = self.get(tenant_id=tenant_id, client_key=client_key)
        if existing is None:
            raise KeyError("idempotency claim does not exist or has expired")
        self._verify_fingerprint(existing, request_fingerprint)
        if existing.claim_token != claim_token:
            raise IdempotencyConflict("idempotency claim belongs to another worker")
        if existing.status == "completed":
            return existing
        completed = IdempotencyRecord(
            request_fingerprint=request_fingerprint,
            claim_token=claim_token,
            status="completed",
            created_at_epoch_seconds=existing.created_at_epoch_seconds,
            response=dict(response),
            completed_at_epoch_seconds=self._clock(),
        )
        key = self._key(tenant_id, client_key)
        if not self._backend.compare_and_set(
            key,
            self._encode(existing),
            self._encode(completed),
            ttl_seconds=self._ttl_seconds,
        ):
            current = self.get(tenant_id=tenant_id, client_key=client_key)
            if current is not None and current == completed:
                return current
            raise IdempotencyConflict("idempotency claim changed before completion")
        return completed

    def abandon(
        self,
        *,
        tenant_id: str,
        client_key: str,
        request_fingerprint: str,
        claim_token: str,
    ) -> bool:
        existing = self.get(tenant_id=tenant_id, client_key=client_key)
        if existing is None:
            return False
        self._verify_fingerprint(existing, request_fingerprint)
        if existing.claim_token != claim_token:
            raise IdempotencyConflict("idempotency claim belongs to another worker")
        return self._backend.compare_and_delete(
            self._key(tenant_id, client_key),
            self._encode(existing),
        )
