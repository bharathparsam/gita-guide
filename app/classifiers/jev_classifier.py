from time import perf_counter
from typing import Any
from uuid import uuid4

import requests

from app.classifiers.taxonomy import EMOTIONS, ROOT_CONFLICTS, SITUATIONS, TAXONOMY_VERSION
from app.config import Settings, get_settings
from app.models.classification import ClassificationResult
from app.observability.logging import (
    current_request_id,
    get_logger,
    prompt_log_fields,
    request_logging_context,
)
from app.observability.metrics import NoOpMetricSink, PhaseOneMetrics
from app.reliability import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    RetryPolicy,
    call_with_resilience,
)


OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_PROMPT_VERSION = "jev-prompt-v1"
logger = get_logger("jev")


class ClassificationError(RuntimeError):
    """Raised when JEV cannot return a valid classification."""


def _choice(
    answers: dict[str, Any], question: str, allowed: dict[str, str]
) -> tuple[str, float]:
    answer = answers.get(question)
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ClassificationError(f"JEV returned an invalid answer for {question}")

    choice = answer.get("choice")
    if choice not in allowed:
        raise ClassificationError(f"JEV returned an unknown {question}: {choice!r}")

    confidence = answer.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise ClassificationError(f"JEV returned invalid confidence for {question}")
    return choice, float(confidence)


class JevClassifier:
    def __init__(
        self,
        settings: Settings,
        session: requests.Session | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        metrics: PhaseOneMetrics | None = None,
    ) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_seconds=settings.circuit_breaker_recovery_seconds,
        )
        self.metrics = metrics or PhaseOneMetrics(NoOpMetricSink())

    def classify(self, message: str) -> ClassificationResult:
        return _classify(
            message,
            self.settings,
            self.session,
            self.circuit_breaker,
            self.metrics,
        )


def _classify(
    message: str,
    settings: Settings,
    session: requests.Session,
    circuit_breaker: CircuitBreaker,
    metrics: PhaseOneMetrics,
) -> ClassificationResult:
    message = message.strip()
    if not message:
        raise ValueError("Message cannot be empty")

    payload = {
        "model": settings.openrouter_model,
        "state": {
            "message": message,
            "task": "Classify one primary label per dimension for reflective Bhagavad Gita guidance.",
            "taxonomy_version": TAXONOMY_VERSION,
            "prompt_version": JEV_PROMPT_VERSION,
        },
        "questions": {
            "in_scope": {
                "type": "noul",
                "instructions": (
                    "Does `message` describe a personal situation, emotional struggle, "
                    "decision, relationship issue, habit, motivation problem, or question "
                    "of purpose for which reflective life guidance could be relevant?"
                ),
                "criteria": {
                    "true": "The message describes a personal concern or inner struggle.",
                    "false": "The message is unrelated, such as a greeting, factual query, or technical task.",
                },
            },
            "primary_situation": {
                "type": "choice",
                "instructions": (
                    "Classify the single primary life situation described in `message`. "
                    "Apply the boundary rules in the criteria literally and do not infer an "
                    "unstated problem merely because it is psychologically possible."
                ),
                "criteria": SITUATIONS,
            },
            "primary_emotion": {
                "type": "choice",
                "instructions": "Classify the primary emotion expressed or implied in `message`.",
                "criteria": EMOTIONS,
            },
            "root_conflict": {
                "type": "choice",
                "instructions": (
                    "Classify the single main underlying inner conflict explicitly supported "
                    "by `message`. Apply the preference rules in the criteria and do not infer "
                    "an unstated dependency on status, reward, or self-worth."
                ),
                "criteria": ROOT_CONFLICTS,
            },
        },
    }

    logger.info(
        "model.prompt.prepared",
        extra={
            "request_id": current_request_id(),
            "stage": "classify_with_jev",
            "provider": "openrouter",
            "model": settings.openrouter_model,
            "prompt_kind": "jev_decision",
            "taxonomy_version": TAXONOMY_VERSION,
            "prompt_version": JEV_PROMPT_VERSION,
            **prompt_log_fields(payload),
        },
    )

    def send_request() -> requests.Response:
        response = session.post(
            OPENROUTER_DECISIONS_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.openrouter_timeout_seconds,
        )
        response.raise_for_status()
        return response

    provider_started = perf_counter()
    provider_status = "error"
    try:
        response = call_with_resilience(
            send_request,
            retry_on=(requests.Timeout, requests.ConnectionError),
            retry_policy=RetryPolicy(max_attempts=settings.provider_max_attempts),
            circuit_breaker=circuit_breaker,
        )
        data = response.json()
        provider_status = "success"
    except CircuitBreakerOpenError as exc:
        provider_status = "circuit_open"
        raise ClassificationError(f"OpenRouter request failed: {exc}") from exc
    except requests.RequestException as exc:
        raise ClassificationError(f"OpenRouter request failed: {exc}") from exc
    except ValueError as exc:
        raise ClassificationError("OpenRouter returned invalid JSON") from exc
    finally:
        metrics.provider_call(
            provider="openrouter",
            operation="jev_classification",
            status=provider_status,
            duration_seconds=perf_counter() - provider_started,
        )

    if not isinstance(data, dict):
        raise ClassificationError("OpenRouter returned an invalid response object")

    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise ClassificationError("OpenRouter response did not contain answers")

    scope_answer = answers.get("in_scope")
    if not isinstance(scope_answer, dict) or scope_answer.get("type") != "noul":
        raise ClassificationError("JEV returned an invalid answer for in_scope")

    scope_probability = scope_answer.get("noul")
    if isinstance(scope_probability, bool) or not isinstance(scope_probability, (int, float)):
        raise ClassificationError("JEV returned an invalid in_scope probability")

    primary_situation, situation_confidence = _choice(
        answers, "primary_situation", SITUATIONS
    )
    primary_emotion, emotion_confidence = _choice(
        answers, "primary_emotion", EMOTIONS
    )
    root_conflict, conflict_confidence = _choice(
        answers, "root_conflict", ROOT_CONFLICTS
    )
    scope_probability = float(scope_probability)
    threshold = settings.classification_scope_threshold
    if scope_probability >= threshold:
        scope_certainty = (
            (scope_probability - threshold) / (1 - threshold) if threshold < 1 else 0.0
        )
    else:
        scope_certainty = (
            (threshold - scope_probability) / threshold if threshold > 0 else 0.0
        )
    confidences = {
        "in_scope": scope_certainty,
        "primary_situation": situation_confidence,
        "primary_emotion": emotion_confidence,
        "root_conflict": conflict_confidence,
    }
    low_confidence_fields = tuple(
        field
        for field, confidence in confidences.items()
        if confidence < settings.classification_min_confidence
    )

    return ClassificationResult(
        in_scope=scope_probability >= settings.classification_scope_threshold,
        in_scope_probability=float(scope_probability),
        primary_situation=primary_situation,
        primary_situation_confidence=situation_confidence,
        primary_emotion=primary_emotion,
        primary_emotion_confidence=emotion_confidence,
        root_conflict=root_conflict,
        root_conflict_confidence=conflict_confidence,
        needs_review=bool(low_confidence_fields),
        low_confidence_fields=low_confidence_fields,
        provider_request_id=data.get("id"),
        model=data.get("model"),
    )


def classify_with_jev(message: str) -> ClassificationResult:
    request_id = current_request_id()
    if request_id is not None:
        return JevClassifier(get_settings()).classify(message)
    with request_logging_context(str(uuid4())):
        return JevClassifier(get_settings()).classify(message)
