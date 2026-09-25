from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.observability.audit import AuditEvent, InMemoryAuditSink, JsonlAuditSink
from app.observability.fingerprint import PromptFingerprinter
from app.observability.metrics import InMemoryMetricSink, MetricKey, PhaseOneMetrics


def test_prompt_fingerprint_is_deterministic_keyed_and_log_safe() -> None:
    first = PromptFingerprinter(b"a" * 32, key_id="2026-09")
    rotated = PromptFingerprinter(b"b" * 32, key_id="2026-10")

    fingerprint = first.fingerprint({"question": "I feel anxious", "step": 1})
    same = first.fingerprint({"step": 1, "question": "I feel anxious"})

    assert fingerprint == same
    assert fingerprint.digest != rotated.fingerprint(
        {"question": "I feel anxious", "step": 1}
    ).digest
    assert fingerprint.as_log_fields() == {
        "prompt_fingerprint": fingerprint.digest,
        "prompt_fingerprint_algorithm": "hmac-sha256-v1",
        "prompt_fingerprint_key_id": "2026-09",
        "prompt_characters": 38,
    }
    assert "a" * 32 not in repr(first)
    assert "I feel anxious" not in repr(fingerprint)


def test_prompt_fingerprinter_rejects_weak_secret() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        PromptFingerprinter(b"too-short", key_id="key-1")


def test_jsonl_audit_sink_persists_versioned_append_only_records(tmp_path) -> None:
    path = tmp_path / "audit" / "events.jsonl"
    sink = JsonlAuditSink(path, fsync=False, create_parents=True)
    event = AuditEvent(
        event_type="phase1.classification.completed",
        request_id="request-123",
        trace_id="trace-456",
        outcome="success",
        occurred_at=datetime(2026, 9, 25, 10, 30, tzinfo=UTC),
        metadata={
            "model_version": "jev-1.13",
            "prompt_fingerprint": "abc123",
            "needs_review": False,
        },
    )

    sink.record(event)
    sink.record(event)

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["schema_version"] == "1"
    assert records[0]["occurred_at"] == "2026-09-25T10:30:00Z"
    assert records[0]["request_id"] == "request-123"
    assert records[0]["metadata"]["prompt_fingerprint"] == "abc123"
    assert path.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    "metadata",
    [
        {"api_key": "do-not-log"},
        {"nested": {"prompt": "raw user text"}},
        {"authorization": "Bearer secret"},
    ],
)
def test_audit_event_rejects_sensitive_metadata(metadata: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="not audit-safe"):
        AuditEvent(
            event_type="phase1.request.completed",
            request_id="request-123",
            outcome="success",
            metadata=metadata,
        )


def test_in_memory_audit_sink_returns_immutable_snapshot() -> None:
    sink = InMemoryAuditSink()
    event = AuditEvent(
        event_type="phase1.guardrail.allowed",
        request_id="request-123",
        outcome="allow",
    )
    sink.record(event)

    assert sink.events == (event,)


def test_audit_metadata_is_defensively_copied_and_immutable() -> None:
    source: dict[str, Any] = {"decision": {"categories": ["harassment"]}}
    event = AuditEvent(
        event_type="phase1.guardrail.blocked",
        request_id="request-123",
        outcome="block",
        metadata=source,
    )
    source["decision"]["categories"].append("changed-after-record")

    assert event.as_dict()["metadata"] == {
        "decision": {"categories": ["harassment"]}
    }
    with pytest.raises(TypeError):
        event.metadata["new"] = "not-allowed"  # type: ignore[index]


def test_phase_one_metrics_use_prometheus_names_and_bounded_labels() -> None:
    sink = InMemoryMetricSink()
    metrics = PhaseOneMetrics(sink)

    metrics.request_started()
    metrics.guardrail_decision(action="allow", provider="nvidia")
    metrics.classification(in_scope=True, needs_review=False)
    metrics.cache_lookup(result="miss")
    metrics.provider_call(
        provider="openrouter",
        operation="classification",
        status="success",
        duration_seconds=0.1,
    )
    metrics.request_finished(status="completed", duration_seconds=0.125)

    assert sink.counters[
        MetricKey("gita_guide_phase_one_requests_started_total", ())
    ] == 1
    assert sink.counters[
        MetricKey(
            "gita_guide_guardrail_decisions_total",
            (("action", "allow"), ("provider", "nvidia")),
        )
    ] == 1
    assert sink.observations[
        MetricKey(
            "gita_guide_phase_one_request_duration_seconds",
            (("status", "completed"),),
        )
    ] == (0.125,)
    assert sink.counters[
        MetricKey(
            "gita_guide_cache_lookups_total",
            (("cache", "classification"), ("result", "miss")),
        )
    ] == 1


def test_metrics_reject_unbounded_or_invalid_shapes() -> None:
    sink = InMemoryMetricSink()

    with pytest.raises(TypeError, match="must be a string"):
        sink.increment("requests_total", labels={"request_id": 123})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="non-negative"):
        sink.increment("requests_total", value=-1)
    with pytest.raises(ValueError, match="Unsupported request status"):
        PhaseOneMetrics(sink).request_finished(status="unknown", duration_seconds=0.1)
    with pytest.raises(ValueError, match="bounded identifier"):
        PhaseOneMetrics(sink).guardrail_decision(
            action="allow",
            provider="request-specific/provider/value",
        )
