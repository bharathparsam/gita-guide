from __future__ import annotations

from langchain_core.runnables import RunnableLambda

from app.models.classification import ClassificationResult
from app.models.retrieval import RetrievalResult
from app.observability.audit import InMemoryAuditSink
from app.observability.metrics import InMemoryMetricSink, MetricKey, PhaseOneMetrics
from app.services.grounding_context_service import invoke_grounding_context_chain


def test_grounding_context_runs_classification_and_retrieval_under_one_request() -> None:
    classification = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.95,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.9,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="attachment_to_results",
        root_conflict_confidence=0.9,
    )
    retrieval = RetrievalResult(
        source="retriever",
        candidate_count=0,
        validation_model="test-validator",
        validation_threshold=0.65,
        ready_for_generation=False,
        chunks=(),
    )
    phase_one = RunnableLambda(
        lambda state: {**state, "classification": classification}
    )
    phase_two = RunnableLambda(
        lambda state: {**state, "retrieval": retrieval}
    )
    audit = InMemoryAuditSink()
    metric_sink = InMemoryMetricSink()

    result = invoke_grounding_context_chain(
        phase_one,
        phase_two,
        "I am anxious",
        request_id="request-one-trace",
        audit_sink=audit,
        metrics=PhaseOneMetrics(metric_sink),
    )

    assert result.request_id == "request-one-trace"
    assert result.classification == classification
    assert result.retrieval == retrieval
    assert audit.events[-1].event_type == "grounding_context.request.finished"
    assert audit.events[-1].outcome == "completed"
    assert metric_sink.counters[
        MetricKey(
            "gita_guide_phase_one_requests_total",
            (("status", "completed"),),
        )
    ] == 1
