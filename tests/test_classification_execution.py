from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock, Thread
from time import sleep
from typing import Any

import pytest

from app.cache import (
    ClassificationCache,
    ClassificationCacheKeyContext,
    HmacCacheKeyBuilder,
    IdempotencyConflict,
    IdempotencyStore,
    InMemoryCacheBackend,
)
from app.models.classification import ClassificationResult
from app.services.classification_execution import ClassificationExecutor


SECRET = "test-secret-that-is-at-least-32-bytes-long"


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
    }
    values.update(overrides)
    return ClassificationResult(**values)


def context() -> ClassificationCacheKeyContext:
    return ClassificationCacheKeyContext(
        tenant_id="tenant-1",
        model_version="jev-1.13",
        taxonomy_version="1.0",
        prompt_version="jev-prompt-v1",
        confidence_threshold=0.6,
        scope_threshold=0.5,
    )


def test_executor_uses_exact_cache_after_guardrail_stage() -> None:
    calls = 0

    def classifier(_: str) -> ClassificationResult:
        nonlocal calls
        calls += 1
        return result()

    backend = InMemoryCacheBackend()
    executor = ClassificationExecutor(
        classifier,
        cache=ClassificationCache(backend, HmacCacheKeyBuilder(SECRET)),
        cache_context=context(),
    )

    first = executor.execute("I feel anxious", tenant_id="tenant-1", idempotency_key=None)
    second = executor.execute(" I  feel anxious ", tenant_id="tenant-1", idempotency_key=None)

    assert first.source == "provider"
    assert second.source == "cache"
    assert calls == 1


def test_executor_replays_completed_idempotent_result() -> None:
    calls = 0

    def classifier(_: str) -> ClassificationResult:
        nonlocal calls
        calls += 1
        return result()

    backend = InMemoryCacheBackend()
    builder = HmacCacheKeyBuilder(SECRET)
    executor = ClassificationExecutor(
        classifier,
        idempotency_store=IdempotencyStore(backend, builder),
    )

    first = executor.execute("message", tenant_id="tenant-1", idempotency_key="retry-1")
    replay = executor.execute("message", tenant_id="tenant-1", idempotency_key="retry-1")

    assert first.source == "provider"
    assert replay.source == "idempotency"
    assert replay.result == first.result
    assert calls == 1


def test_executor_rejects_reused_idempotency_key_for_different_message() -> None:
    backend = InMemoryCacheBackend()
    executor = ClassificationExecutor(
        lambda _: result(),
        idempotency_store=IdempotencyStore(backend, HmacCacheKeyBuilder(SECRET)),
    )
    executor.execute("first", tenant_id="tenant-1", idempotency_key="same")

    with pytest.raises(IdempotencyConflict):
        executor.execute("second", tenant_id="tenant-1", idempotency_key="same")


def test_executor_singleflight_coalesces_provider_calls() -> None:
    calls = 0
    lock = Lock()
    started = Event()
    release = Event()

    def classifier(_: str) -> ClassificationResult:
        nonlocal calls
        with lock:
            calls += 1
        started.set()
        assert release.wait(timeout=2)
        return result()

    executor = ClassificationExecutor(
        classifier,
        cache=ClassificationCache(
            InMemoryCacheBackend(), HmacCacheKeyBuilder(SECRET)
        ),
        cache_context=context(),
    )
    sources: list[str] = []

    def invoke() -> None:
        sources.append(
            executor.execute("same", tenant_id="tenant-1", idempotency_key=None).source
        )

    leader = Thread(target=invoke)
    follower = Thread(target=invoke)
    leader.start()
    assert started.wait(timeout=2)
    follower.start()
    release.set()
    leader.join(timeout=2)
    follower.join(timeout=2)

    assert calls == 1
    assert sorted(sources) == ["coalesced", "provider"]


def test_concurrent_cache_smoke_coalesces_fifty_identical_requests() -> None:
    calls = 0
    lock = Lock()

    def classifier(_: str) -> ClassificationResult:
        nonlocal calls
        with lock:
            calls += 1
        sleep(0.02)
        return result()

    executor = ClassificationExecutor(
        classifier,
        cache=ClassificationCache(
            InMemoryCacheBackend(), HmacCacheKeyBuilder(SECRET)
        ),
        cache_context=context(),
    )

    with ThreadPoolExecutor(max_workers=16) as pool:
        outputs = list(
            pool.map(
                lambda _: executor.execute(
                    "same message",
                    tenant_id="tenant-1",
                    idempotency_key=None,
                ),
                range(50),
            )
        )

    assert len(outputs) == 50
    assert calls == 1
    assert {output.source for output in outputs} <= {
        "provider",
        "coalesced",
        "cache",
    }
