from prometheus_client import CollectorRegistry

from app.observability.prometheus import PrometheusMetricSink


def test_prometheus_sink_renders_counters_and_histograms() -> None:
    sink = PrometheusMetricSink(CollectorRegistry())

    sink.increment("gita_guide_requests_total", labels={"status": "completed"})
    sink.observe(
        "gita_guide_request_duration_seconds",
        0.25,
        labels={"status": "completed"},
    )
    output = sink.render().decode()

    assert 'gita_guide_requests_total{status="completed"} 1.0' in output
    assert "gita_guide_request_duration_seconds_count" in output
