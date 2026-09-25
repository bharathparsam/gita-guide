import logging
from dataclasses import replace
from unittest.mock import Mock

import pytest
import requests

from app.classifiers.jev_classifier import ClassificationError, JevClassifier
from app.config import Settings
from app.guardrails.input_safety import (
    InputSafetyEscalation,
    InputSafetyRejection,
    LexicalInputGuardrail,
)
from app.models.classification import ClassificationResult
from app.services.classification_service import classify
from app.services.classification_execution import ClassificationExecutor
from app.observability.audit import InMemoryAuditSink
from app.observability.metrics import InMemoryMetricSink, PhaseOneMetrics


def settings() -> Settings:
    return Settings(
        openrouter_api_key="test-key",
        openrouter_model="typesafe/jev-1.13",
        openrouter_timeout_seconds=3,
        classification_scope_threshold=0.5,
        classification_min_confidence=0.6,
        nvidia_guardrail_url=None,
        nvidia_guardrail_model="test-safety-model",
        nvidia_guardrail_api_key="EMPTY",
        nvidia_guardrail_required=False,
    )


def successful_response() -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "id": "decision-123",
        "model": "typesafe/jev-1.13-snapshot",
        "answers": {
            "in_scope": {"type": "noul", "noul": 0.98},
            "primary_situation": {
                "type": "choice",
                "choice": "fear_of_failure",
                "confidence": 0.93,
            },
            "primary_emotion": {
                "type": "choice",
                "choice": "sadness",
                "confidence": 0.88,
            },
            "root_conflict": {
                "type": "choice",
                "choice": "attachment_to_results",
                "confidence": 0.91,
            },
        },
    }
    return response


def test_jev_classifier_returns_validated_result() -> None:
    session = Mock()
    session.post.return_value = successful_response()

    result = JevClassifier(settings(), session=session).classify(
        "I failed an interview and now feel useless."
    )

    assert result.in_scope is True
    assert result.in_scope_probability == 0.98
    assert result.primary_situation == "fear_of_failure"
    assert result.primary_situation_confidence == 0.93
    assert result.needs_review is False
    assert result.provider_request_id == "decision-123"
    payload = session.post.call_args.kwargs["json"]
    assert set(payload["questions"]) == {
        "in_scope",
        "primary_situation",
        "primary_emotion",
        "root_conflict",
    }


def test_jev_model_prompt_emits_an_audit_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOG_PROMPT_CONTENT", raising=False)
    session = Mock()
    session.post.return_value = successful_response()
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    jev_logger = logging.getLogger("gita_guide.jev")
    previous_level = jev_logger.level
    handler = CaptureHandler()
    jev_logger.setLevel(logging.INFO)
    jev_logger.addHandler(handler)
    try:
        JevClassifier(settings(), session=session).classify("I feel stuck")
    finally:
        jev_logger.removeHandler(handler)
        jev_logger.setLevel(previous_level)

    prompt_record = next(
        record for record in records if record.getMessage() == "model.prompt.prepared"
    )
    assert prompt_record.prompt_kind == "jev_decision"  # type: ignore[attr-defined]
    assert prompt_record.taxonomy_version  # type: ignore[attr-defined]
    assert len(prompt_record.prompt_fingerprint) == 64  # type: ignore[attr-defined]
    assert (
        prompt_record.prompt_fingerprint_algorithm == "hmac-sha256-v1"  # type: ignore[attr-defined]
    )
    assert not hasattr(prompt_record, "prompt")


def test_jev_classifier_rejects_unknown_taxonomy_label() -> None:
    session = Mock()
    response = successful_response()
    response.json.return_value["answers"]["primary_situation"]["choice"] = "unknown"
    session.post.return_value = response

    with pytest.raises(ClassificationError, match="unknown primary_situation"):
        JevClassifier(settings(), session=session).classify("I feel stuck")


def test_jev_classifier_routes_low_confidence_for_review() -> None:
    session = Mock()
    response = successful_response()
    response.json.return_value["answers"]["root_conflict"]["confidence"] = 0.31
    session.post.return_value = response

    result = JevClassifier(settings(), session=session).classify("I cannot decide")

    assert result.needs_review is True
    assert result.low_confidence_fields == ("root_conflict",)


def test_jev_retries_a_transient_connection_failure() -> None:
    session = Mock()
    session.post.side_effect = [
        requests.ConnectionError("temporary"),
        successful_response(),
    ]

    result = JevClassifier(settings(), session=session).classify("I feel stuck")

    assert result.in_scope is True
    assert session.post.call_count == 2


def test_jev_circuit_breaker_stops_calls_while_provider_is_down() -> None:
    session = Mock()
    session.post.side_effect = requests.ConnectionError("down")
    classifier = JevClassifier(
        replace(
            settings(),
            provider_max_attempts=1,
            circuit_breaker_failure_threshold=1,
        ),
        session=session,
    )

    with pytest.raises(ClassificationError, match="request failed"):
        classifier.classify("I feel stuck")
    with pytest.raises(ClassificationError, match="circuit is open"):
        classifier.classify("I still feel stuck")

    assert session.post.call_count == 1


def test_service_does_not_call_classifier_for_explicit_input() -> None:
    classifier = Mock()

    with pytest.raises(InputSafetyRejection):
        classify(
            "This is f***ing unacceptable",
            classifier=classifier,
            guardrail=LexicalInputGuardrail(),
        )

    classifier.assert_not_called()


def test_guardrail_runs_before_classification_cache_executor() -> None:
    executor = Mock(spec=ClassificationExecutor)

    with pytest.raises(InputSafetyRejection):
        classify(
            "This is f***ing unacceptable",
            guardrail=LexicalInputGuardrail(),
            classification_executor=executor,
        )

    executor.execute.assert_not_called()


def test_service_escalates_self_harm_before_classification() -> None:
    classifier = Mock()

    with pytest.raises(InputSafetyEscalation):
        classify(
            "I want to end my life",
            classifier=classifier,
            guardrail=LexicalInputGuardrail(),
        )

    classifier.assert_not_called()


def test_service_passes_safe_input_to_classifier() -> None:
    expected = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.9,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.8,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="uncertainty",
        root_conflict_confidence=0.85,
    )
    classifier = Mock(return_value=expected)

    result = classify(
        "I am anxious while waiting for my exam result",
        classifier=classifier,
        guardrail=LexicalInputGuardrail(),
    )

    assert result == expected
    classifier.assert_called_once()


def test_phase_one_logs_every_prompt_with_correlation_id() -> None:
    expected = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.9,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.8,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="uncertainty",
        root_conflict_confidence=0.85,
    )
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    phase_logger = logging.getLogger("gita_guide.phase_one")
    previous_level = phase_logger.level
    handler = CaptureHandler()
    phase_logger.setLevel(logging.INFO)
    phase_logger.addHandler(handler)
    try:
        classify(
            "I am anxious while waiting for my result",
            classifier=Mock(return_value=expected),
            guardrail=LexicalInputGuardrail(),
            request_id="request-123",
            include_prompt_content=False,
        )
    finally:
        phase_logger.removeHandler(handler)
        phase_logger.setLevel(previous_level)

    prompt_record = next(
        record for record in records if record.getMessage() == "phase1.prompt.received"
    )
    assert prompt_record.request_id == "request-123"  # type: ignore[attr-defined]
    assert len(prompt_record.prompt_fingerprint) == 64  # type: ignore[attr-defined]
    assert not hasattr(prompt_record, "prompt")
    assert any(record.getMessage() == "phase1.request.completed" for record in records)


def test_raw_prompt_logging_requires_explicit_opt_in() -> None:
    expected = ClassificationResult(
        in_scope=False,
        in_scope_probability=0.1,
        primary_situation="other",
        primary_situation_confidence=0.9,
        primary_emotion="other",
        primary_emotion_confidence=0.9,
        root_conflict="other",
        root_conflict_confidence=0.9,
    )
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    phase_logger = logging.getLogger("gita_guide.phase_one")
    previous_level = phase_logger.level
    handler = CaptureHandler()
    phase_logger.setLevel(logging.INFO)
    phase_logger.addHandler(handler)
    try:
        classify(
            "hello",
            classifier=Mock(return_value=expected),
            guardrail=LexicalInputGuardrail(),
            include_prompt_content=True,
        )
    finally:
        phase_logger.removeHandler(handler)
        phase_logger.setLevel(previous_level)

    prompt_record = next(
        record for record in records if record.getMessage() == "phase1.prompt.received"
    )
    assert prompt_record.prompt == "hello"  # type: ignore[attr-defined]


def test_phase_one_records_audit_events_and_metrics() -> None:
    expected = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.9,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.8,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="uncertainty",
        root_conflict_confidence=0.85,
    )
    audit = InMemoryAuditSink()
    metric_sink = InMemoryMetricSink()

    classify(
        "I am worried about my result",
        classifier=Mock(return_value=expected),
        guardrail=LexicalInputGuardrail(),
        audit_sink=audit,
        metrics=PhaseOneMetrics(metric_sink),
        request_id="audit-123",
    )

    assert [event.event_type for event in audit.events] == [
        "phase1.input.validated",
        "phase1.guardrail.decision",
        "phase1.classification.completed",
        "phase1.request.finished",
    ]
    assert all(event.request_id == "audit-123" for event in audit.events)
    metric_names = {key.name for key in metric_sink.counters}
    assert "gita_guide_phase_one_requests_started_total" in metric_names
    assert "gita_guide_classifications_total" in metric_names
