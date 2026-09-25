"""Low-cardinality metrics boundary for Phase 1.

The protocol maps directly to Prometheus counters and histograms while keeping
the domain layer independent of a metrics vendor.  Never use request, user, or
prompt identifiers as metric labels; those belong in logs and traces.
"""

from __future__ import annotations

import math
import re
import threading
from collections import defaultdict
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol


METRIC_PREFIX = "gita_guide"
_METRIC_NAME_PATTERN = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_LABEL_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_BOUNDED_LABEL_VALUE_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")


LabelSet = tuple[tuple[str, str], ...]


def _metric_name(name: str) -> str:
    resolved = name if name.startswith(f"{METRIC_PREFIX}_") else f"{METRIC_PREFIX}_{name}"
    if not _METRIC_NAME_PATTERN.fullmatch(resolved):
        raise ValueError(f"Invalid metric name: {name!r}")
    return resolved


def _labels(labels: Mapping[str, str] | None) -> LabelSet:
    if not labels:
        return ()
    normalized: list[tuple[str, str]] = []
    for key, value in labels.items():
        if not _LABEL_NAME_PATTERN.fullmatch(key):
            raise ValueError(f"Invalid metric label name: {key!r}")
        if not isinstance(value, str):
            raise TypeError(f"Metric label {key!r} must be a string")
        normalized.append((key, value))
    return tuple(sorted(normalized))


def _bounded_label(value: str, *, name: str) -> str:
    if not _BOUNDED_LABEL_VALUE_PATTERN.fullmatch(value):
        raise ValueError(f"Metric label {name!r} is not a bounded identifier")
    return value


class MetricSink(Protocol):
    def increment(
        self,
        name: str,
        *,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None: ...


class NoOpMetricSink:
    def increment(
        self,
        name: str,
        *,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        del name, value, labels

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        del name, value, labels


@dataclass(frozen=True, slots=True)
class MetricKey:
    name: str
    labels: LabelSet


class InMemoryMetricSink:
    """Thread-safe sink that exposes snapshots for deterministic tests."""

    def __init__(self) -> None:
        self._counters: dict[MetricKey, float] = defaultdict(float)
        self._observations: dict[MetricKey, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def increment(
        self,
        name: str,
        *,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        if not math.isfinite(value) or value < 0:
            raise ValueError("Counter increments must be finite and non-negative")
        key = MetricKey(_metric_name(name), _labels(labels))
        with self._lock:
            self._counters[key] += value

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        if not math.isfinite(value):
            raise ValueError("Metric observations must be finite")
        key = MetricKey(_metric_name(name), _labels(labels))
        with self._lock:
            self._observations[key].append(value)

    @property
    def counters(self) -> dict[MetricKey, float]:
        with self._lock:
            return dict(self._counters)

    @property
    def observations(self) -> dict[MetricKey, tuple[float, ...]]:
        with self._lock:
            return {key: tuple(values) for key, values in self._observations.items()}


@contextmanager
def observe_duration(
    sink: MetricSink,
    name: str,
    *,
    labels: Mapping[str, str] | None = None,
) -> Iterator[None]:
    """Measure a block in seconds, including failed execution."""
    started = perf_counter()
    try:
        yield
    finally:
        sink.observe(name, perf_counter() - started, labels=labels)


class PhaseOneMetrics:
    """Stable names and bounded labels for the Phase 1 service."""

    def __init__(self, sink: MetricSink) -> None:
        self._sink = sink

    def request_started(self) -> None:
        self._sink.increment("phase_one_requests_started_total")

    def request_finished(self, *, status: str, duration_seconds: float) -> None:
        if status not in {"completed", "rejected", "failed"}:
            raise ValueError(f"Unsupported request status: {status!r}")
        labels = {"status": status}
        self._sink.increment("phase_one_requests_total", labels=labels)
        self._sink.observe("phase_one_request_duration_seconds", duration_seconds, labels=labels)

    def guardrail_decision(self, *, action: str, provider: str) -> None:
        if action not in {"allow", "block", "escalate"}:
            raise ValueError(f"Unsupported guardrail action: {action!r}")
        self._sink.increment(
            "guardrail_decisions_total",
            labels={"action": action, "provider": _bounded_label(provider, name="provider")},
        )

    def classification(self, *, in_scope: bool, needs_review: bool) -> None:
        self._sink.increment(
            "classifications_total",
            labels={
                "in_scope": str(in_scope).lower(),
                "needs_review": str(needs_review).lower(),
            },
        )

    def cache_lookup(self, *, result: str, cache: str = "classification") -> None:
        if result not in {"hit", "miss", "error"}:
            raise ValueError(f"Unsupported cache result: {result!r}")
        self._sink.increment(
            "cache_lookups_total",
            labels={
                "cache": _bounded_label(cache, name="cache"),
                "result": result,
            },
        )

    def provider_call(
        self,
        *,
        provider: str,
        operation: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        if status not in {"success", "error", "circuit_open"}:
            raise ValueError(f"Unsupported provider status: {status!r}")
        labels = {
            "operation": _bounded_label(operation, name="operation"),
            "provider": _bounded_label(provider, name="provider"),
            "status": status,
        }
        self._sink.increment("provider_calls_total", labels=labels)
        self._sink.observe("provider_call_duration_seconds", duration_seconds, labels=labels)
