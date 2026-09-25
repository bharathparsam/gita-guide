from __future__ import annotations

from threading import Event, Lock, Thread
from typing import Any

import pytest

from app.cache import (
    ClassificationCache,
    ClassificationCacheKeyContext,
    ClassificationCachePolicy,
    HmacCacheKeyBuilder,
    IdempotencyConflict,
    IdempotencyStore,
    InMemoryCacheBackend,
    RedisCacheBackend,
    SingleFlight,
    UpstashRedisCacheBackend,
)
from app.models.classification import ClassificationResult


SECRET = "test-secret-that-is-at-least-32-bytes-long"


class Clock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def context(**overrides: Any) -> ClassificationCacheKeyContext:
    values = {
        "tenant_id": "tenant-1",
        "model_version": "jev-1.13",
        "taxonomy_version": "taxonomy-v1",
        "prompt_version": "prompt-v2",
        "confidence_threshold": 0.6,
        "scope_threshold": 0.5,
    }
    values.update(overrides)
    return ClassificationCacheKeyContext(**values)


def result(**overrides: Any) -> ClassificationResult:
    values = {
        "in_scope": True,
        "in_scope_probability": 0.95,
        "primary_situation": "outcome_anxiety",
        "primary_situation_confidence": 0.9,
        "primary_emotion": "fear",
        "primary_emotion_confidence": 0.91,
        "root_conflict": "attachment_to_results",
        "root_conflict_confidence": 0.88,
        "needs_review": False,
    }
    values.update(overrides)
    return ClassificationResult(**values)


def test_hmac_key_is_normalized_versioned_and_opaque() -> None:
    builder = HmacCacheKeyBuilder(SECRET)
    first = builder.classification_key("  I\tfeel   anxious  ", context())
    second = builder.classification_key("I feel anxious", context())

    assert first == second
    assert first.startswith("classification:v1:")
    assert "anxious" not in first
    assert first != builder.classification_key(
        "I feel anxious", context(prompt_version="prompt-v3")
    )
    assert first != builder.classification_key(
        "I feel anxious", context(tenant_id="tenant-2")
    )


def test_classification_cache_round_trip_and_ttl() -> None:
    clock = Clock()
    backend = InMemoryCacheBackend(clock=clock)
    cache = ClassificationCache(
        backend,
        HmacCacheKeyBuilder(SECRET),
        policy=ClassificationCachePolicy(ttl_seconds=10),
        clock=clock,
    )

    assert cache.put("I feel anxious", context(), result()) is True
    cached = cache.get("I feel anxious", context())
    assert cached is not None
    assert cached.result == result()
    assert cached.stored_at_epoch_seconds == 1_000.0

    clock.value += 10
    assert cache.get("I feel anxious", context()) is None


@pytest.mark.parametrize(
    "classification",
    [
        result(needs_review=True),
        result(low_confidence_fields=("root_conflict",)),
        result(primary_emotion_confidence=0.59),
    ],
)
def test_classification_cache_rejects_review_and_low_confidence_results(
    classification: ClassificationResult,
) -> None:
    cache = ClassificationCache(
        InMemoryCacheBackend(),
        HmacCacheKeyBuilder(SECRET),
    )

    assert cache.put("message", context(), classification) is False
    assert cache.get("message", context()) is None


def test_confident_out_of_scope_result_can_be_cached() -> None:
    cache = ClassificationCache(
        InMemoryCacheBackend(),
        HmacCacheKeyBuilder(SECRET),
    )
    classification = result(in_scope=False, in_scope_probability=0.05)

    assert cache.put("weather tomorrow", context(), classification) is True


def test_context_confidence_threshold_is_enforced_even_for_inconsistent_result() -> None:
    cache = ClassificationCache(
        InMemoryCacheBackend(),
        HmacCacheKeyBuilder(SECRET),
    )

    assert cache.put(
        "message",
        context(confidence_threshold=0.92),
        result(needs_review=False),
    ) is False


def test_corrupt_classification_entry_is_removed_and_treated_as_miss() -> None:
    backend = InMemoryCacheBackend()
    cache = ClassificationCache(backend, HmacCacheKeyBuilder(SECRET))
    key = cache.key_for("message", context())
    backend.set(key, b"not-json", ttl_seconds=30)

    assert cache.get("message", context()) is None
    assert backend.get(key) is None


def test_idempotency_claim_completion_conflict_and_error_abandonment() -> None:
    clock = Clock()
    store = IdempotencyStore(
        InMemoryCacheBackend(clock=clock),
        HmacCacheKeyBuilder(SECRET),
        ttl_seconds=30,
        clock=clock,
    )
    fingerprint = store.fingerprint({"message": "hello"})

    first = store.claim(
        tenant_id="tenant-1",
        client_key="retry-123",
        request_fingerprint=fingerprint,
    )
    duplicate = store.claim(
        tenant_id="tenant-1",
        client_key="retry-123",
        request_fingerprint=fingerprint,
    )
    assert first.acquired is True
    assert duplicate.acquired is False
    assert duplicate.record.status == "in_progress"

    completed = store.complete(
        tenant_id="tenant-1",
        client_key="retry-123",
        request_fingerprint=fingerprint,
        claim_token=first.record.claim_token,
        response={"status": "ok"},
    )
    assert completed.status == "completed"
    assert completed.response == {"status": "ok"}

    other_fingerprint = store.fingerprint({"message": "other"})
    with pytest.raises(IdempotencyConflict):
        store.claim(
            tenant_id="tenant-1",
            client_key="retry-123",
            request_fingerprint=other_fingerprint,
        )

    error_claim = store.claim(
        tenant_id="tenant-1",
        client_key="retry-error",
        request_fingerprint=fingerprint,
    )
    assert error_claim.acquired
    assert store.abandon(
        tenant_id="tenant-1",
        client_key="retry-error",
        request_fingerprint=fingerprint,
        claim_token=error_claim.record.claim_token,
    )
    assert store.get(tenant_id="tenant-1", client_key="retry-error") is None


def test_expired_idempotency_claim_cannot_delete_new_owner() -> None:
    clock = Clock()
    store = IdempotencyStore(
        InMemoryCacheBackend(clock=clock),
        HmacCacheKeyBuilder(SECRET),
        ttl_seconds=10,
        clock=clock,
    )
    fingerprint = store.fingerprint({"message": "hello"})
    stale = store.claim(
        tenant_id="tenant-1",
        client_key="retry-123",
        request_fingerprint=fingerprint,
    )
    clock.value += 10
    current = store.claim(
        tenant_id="tenant-1",
        client_key="retry-123",
        request_fingerprint=fingerprint,
    )

    assert stale.record.claim_token != current.record.claim_token
    with pytest.raises(IdempotencyConflict, match="another worker"):
        store.abandon(
            tenant_id="tenant-1",
            client_key="retry-123",
            request_fingerprint=fingerprint,
            claim_token=stale.record.claim_token,
        )
    assert store.get(tenant_id="tenant-1", client_key="retry-123") == current.record


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.calls: list[tuple[str, int, bool]] = []

    def get(self, name: str) -> bytes | None:
        return self.values.get(name)

    def set(
        self, name: str, value: bytes, *, ex: int, nx: bool = False
    ) -> bool | None:
        self.calls.append((name, ex, nx))
        if nx and name in self.values:
            return None
        self.values[name] = value
        return True

    def delete(self, *names: str) -> int:
        count = 0
        for name in names:
            if name in self.values:
                del self.values[name]
                count += 1
        return count


def test_redis_backend_namespaces_keys_and_uses_atomic_set_nx() -> None:
    redis = FakeRedis()
    backend = RedisCacheBackend(redis, namespace="gita:test")

    assert backend.set_if_absent("key", b"one", ttl_seconds=12) is True
    assert backend.set_if_absent("key", b"two", ttl_seconds=12) is False
    assert backend.get("key") == b"one"
    assert redis.calls[0] == ("gita:test:key", 12, True)


class FakeUpstashRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.calls: list[tuple[str, int, bool | None]] = []

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
        nx: bool | None = None,
    ) -> str | None:
        self.calls.append((key, ex, nx))
        if nx and key in self.values:
            return None
        self.values[key] = value
        return "OK"

    def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.values:
                del self.values[key]
                deleted += 1
        return deleted

    def eval(
        self,
        script: str,
        *,
        keys: list[str] | None = None,
        args: list[str] | None = None,
    ) -> int:
        assert keys is not None and args is not None
        key = keys[0]
        if self.values.get(key) != args[0]:
            return 0
        if "ARGV[2]" in script:
            self.values[key] = args[1]
        else:
            del self.values[key]
        return 1


def test_upstash_backend_round_trips_bytes_and_uses_atomic_operations() -> None:
    redis = FakeUpstashRedis()
    backend = UpstashRedisCacheBackend(redis, namespace="gita:test")

    assert backend.set_if_absent("key", b"one\x00", ttl_seconds=12) is True
    assert backend.set_if_absent("key", b"two", ttl_seconds=12) is False
    assert backend.get("key") == b"one\x00"
    assert redis.values["gita:test:key"] != "one\x00"
    assert backend.compare_and_set(
        "key", b"one\x00", b"two", ttl_seconds=18
    ) is True
    assert backend.get("key") == b"two"
    assert backend.compare_and_delete("key", b"wrong") is False
    assert backend.compare_and_delete("key", b"two") is True
    assert backend.get("key") is None
    assert redis.calls[0] == ("gita:test:key", 12, True)


def test_singleflight_coalesces_concurrent_operations() -> None:
    flight = SingleFlight()
    operation_started = Event()
    release_operation = Event()
    call_count = 0
    count_lock = Lock()
    outputs: list[tuple[str, bool]] = []

    def operation() -> str:
        nonlocal call_count
        with count_lock:
            call_count += 1
        operation_started.set()
        assert release_operation.wait(timeout=2)
        return "classification"

    def invoke() -> None:
        output = flight.do("same-cache-key", operation)
        outputs.append((output.value, output.shared))

    leader = Thread(target=invoke)
    follower = Thread(target=invoke)
    leader.start()
    assert operation_started.wait(timeout=2)
    follower.start()
    release_operation.set()
    leader.join(timeout=2)
    follower.join(timeout=2)

    assert not leader.is_alive() and not follower.is_alive()
    assert call_count == 1
    assert sorted(outputs) == [
        ("classification", False),
        ("classification", True),
    ]
