from __future__ import annotations

from collections.abc import Mapping
from threading import Lock

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from app.observability.metrics import MetricSink


class PrometheusMetricSink(MetricSink):
    """Lazy Prometheus adapter for the low-cardinality metric boundary."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry(auto_describe=True)
        self._counters: dict[tuple[str, tuple[str, ...]], Counter] = {}
        self._histograms: dict[tuple[str, tuple[str, ...]], Histogram] = {}
        self._lock = Lock()

    @staticmethod
    def _label_parts(labels: Mapping[str, str] | None) -> tuple[tuple[str, ...], dict[str, str]]:
        values = dict(labels or {})
        return tuple(sorted(values)), values

    @staticmethod
    def _name(name: str) -> str:
        return name if name.startswith("gita_guide_") else f"gita_guide_{name}"

    def increment(
        self,
        name: str,
        *,
        value: float = 1.0,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        label_names, label_values = self._label_parts(labels)
        name = self._name(name)
        key = (name, label_names)
        with self._lock:
            metric = self._counters.get(key)
            if metric is None:
                metric = Counter(
                    name,
                    f"Gita Guide {name}",
                    labelnames=label_names,
                    registry=self.registry,
                )
                self._counters[key] = metric
        if label_names:
            metric.labels(**label_values).inc(value)
        else:
            metric.inc(value)

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: Mapping[str, str] | None = None,
    ) -> None:
        label_names, label_values = self._label_parts(labels)
        name = self._name(name)
        key = (name, label_names)
        with self._lock:
            metric = self._histograms.get(key)
            if metric is None:
                metric = Histogram(
                    name,
                    f"Gita Guide {name}",
                    labelnames=label_names,
                    registry=self.registry,
                )
                self._histograms[key] = metric
        if label_names:
            metric.labels(**label_values).observe(value)
        else:
            metric.observe(value)

    def render(self) -> bytes:
        return generate_latest(self.registry)
