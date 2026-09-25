from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import TypedDict, cast
from uuid import uuid4

from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from app.classifiers.jev_classifier import classify_with_jev
from app.guardrails.input_safety import (
    InputGuardrail,
    InputSafetyAction,
    InputSafetyEscalation,
    InputSafetyRejection,
    build_input_guardrail,
)
from app.models.classification import ClassificationResult
from app.observability.audit import AuditEvent, AuditSink, NoOpAuditSink
from app.observability.logging import (
    get_logger,
    prompt_log_fields,
    request_logging_context,
)
from app.observability.metrics import NoOpMetricSink, PhaseOneMetrics
from app.services.classification_execution import ClassificationExecutor


logger = get_logger("phase_one")


class PhaseOneState(TypedDict, total=False):
    message: str
    request_id: str
    safety_provider: str
    classification: ClassificationResult
    classification_source: str
    cache_age_seconds: float | None
    tenant_id: str
    idempotency_key: str | None


def build_phase_one_chain(
    *,
    classifier: Callable[[str], ClassificationResult] | None = None,
    guardrail: InputGuardrail | None = None,
    include_prompt_content: bool | None = None,
    classification_executor: ClassificationExecutor | None = None,
    audit_sink: AuditSink | None = None,
    metrics: PhaseOneMetrics | None = None,
) -> Runnable[PhaseOneState, PhaseOneState]:
    """Build the traceable Phase 1 LangChain pipeline."""
    resolved_classifier = classifier or classify_with_jev
    resolved_guardrail = guardrail or build_input_guardrail()
    resolved_executor = classification_executor or ClassificationExecutor(
        resolved_classifier
    )
    resolved_audit = audit_sink or NoOpAuditSink()
    resolved_metrics = metrics or PhaseOneMetrics(NoOpMetricSink())

    def validate_input(state: PhaseOneState) -> PhaseOneState:
        request_id = state["request_id"]
        raw_message = state.get("message")
        prompt = raw_message if isinstance(raw_message, str) else str(raw_message)
        safe_prompt_fields = prompt_log_fields(prompt, include_content=False)
        logger.info(
            "phase1.prompt.received",
            extra={
                "request_id": request_id,
                "stage": "validate_input",
                **prompt_log_fields(prompt, include_content=include_prompt_content),
            },
        )
        if not isinstance(raw_message, str):
            raise ValueError("Message must be a string")
        message = raw_message.strip()
        if not message:
            raise ValueError("Message cannot be empty")
        resolved_audit.record(
            AuditEvent(
                event_type="phase1.input.validated",
                request_id=request_id,
                outcome="accepted",
                metadata={
                    "fingerprint": safe_prompt_fields["prompt_fingerprint"],
                    "fingerprint_algorithm": safe_prompt_fields[
                        "prompt_fingerprint_algorithm"
                    ],
                    "fingerprint_key_id": safe_prompt_fields[
                        "prompt_fingerprint_key_id"
                    ],
                    "characters": safe_prompt_fields["prompt_characters"],
                },
            )
        )
        return {
            "message": message,
            "request_id": request_id,
            "tenant_id": state.get("tenant_id", "default"),
            "idempotency_key": state.get("idempotency_key"),
        }

    def validate_safety(state: PhaseOneState) -> PhaseOneState:
        started = perf_counter()
        decision = resolved_guardrail.check(state["message"])
        log_fields = {
            "request_id": state["request_id"],
            "stage": "validate_safety",
            "action": decision.action.value,
            "categories": decision.categories,
            "provider": decision.provider,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
        }
        resolved_metrics.guardrail_decision(
            action=decision.action.value,
            provider=decision.provider,
        )
        resolved_audit.record(
            AuditEvent(
                event_type="phase1.guardrail.decision",
                request_id=state["request_id"],
                outcome=decision.action.value,
                metadata={
                    "provider": decision.provider,
                    "categories": decision.categories,
                },
            )
        )
        if decision.action is InputSafetyAction.BLOCK:
            logger.warning("phase1.guardrail.blocked", extra=log_fields)
            raise InputSafetyRejection(decision)
        if decision.action is InputSafetyAction.ESCALATE:
            logger.warning("phase1.guardrail.escalated", extra=log_fields)
            raise InputSafetyEscalation(decision)
        logger.info("phase1.guardrail.allowed", extra=log_fields)
        return {**state, "safety_provider": decision.provider}

    def classify_intent(state: PhaseOneState) -> PhaseOneState:
        started = perf_counter()
        execution = resolved_executor.execute(
            state["message"],
            tenant_id=state.get("tenant_id", "default"),
            idempotency_key=state.get("idempotency_key"),
        )
        result = execution.result
        if execution.source in {"cache", "idempotency"}:
            resolved_metrics.cache_lookup(result="hit", cache=execution.source)
        elif execution.source == "provider":
            resolved_metrics.cache_lookup(result="miss")
        logger.info(
            "phase1.classification.completed",
            extra={
                "request_id": state["request_id"],
                "stage": "classify_intent",
                "model": result.model,
                "provider_request_id": result.provider_request_id,
                "in_scope": result.in_scope,
                "primary_situation": result.primary_situation,
                "primary_emotion": result.primary_emotion,
                "root_conflict": result.root_conflict,
                "needs_review": result.needs_review,
                "classification_source": execution.source,
                "cache_age_seconds": execution.cache_age_seconds,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        resolved_metrics.classification(
            in_scope=result.in_scope,
            needs_review=result.needs_review,
        )
        resolved_audit.record(
            AuditEvent(
                event_type="phase1.classification.completed",
                request_id=state["request_id"],
                outcome="needs_review" if result.needs_review else "accepted",
                metadata={
                    "source": execution.source,
                    "model": result.model or "unknown",
                    "provider_request_id": result.provider_request_id or "unknown",
                    "in_scope": result.in_scope,
                    "primary_situation": result.primary_situation,
                    "primary_emotion": result.primary_emotion,
                    "root_conflict": result.root_conflict,
                },
            )
        )
        return {
            **state,
            "classification": result,
            "classification_source": execution.source,
            "cache_age_seconds": execution.cache_age_seconds,
        }

    validate = RunnableLambda(validate_input).with_config(run_name="validate_input")
    safety = RunnableLambda(validate_safety).with_config(run_name="validate_input_safety")
    classification = RunnableLambda(classify_intent).with_config(run_name="classify_with_jev")
    return cast(
        Runnable[PhaseOneState, PhaseOneState],
        (validate | safety | classification).with_config(
            run_name="phase_one_classification",
            tags=["phase-1", "classification"],
        ),
    )


def classify(
    message: str,
    *,
    classifier: Callable[[str], ClassificationResult] | None = None,
    guardrail: InputGuardrail | None = None,
    request_id: str | None = None,
    include_prompt_content: bool | None = None,
    tenant_id: str = "default",
    idempotency_key: str | None = None,
    classification_executor: ClassificationExecutor | None = None,
    audit_sink: AuditSink | None = None,
    metrics: PhaseOneMetrics | None = None,
) -> ClassificationResult:
    chain = build_phase_one_chain(
        classifier=classifier,
        guardrail=guardrail,
        include_prompt_content=include_prompt_content,
        classification_executor=classification_executor,
        audit_sink=audit_sink,
        metrics=metrics,
    )
    return invoke_phase_one_chain(
        chain,
        message,
        request_id=request_id,
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        audit_sink=audit_sink,
        metrics=metrics,
    )


def invoke_phase_one_chain(
    chain: Runnable[PhaseOneState, PhaseOneState],
    message: str,
    *,
    request_id: str | None = None,
    tenant_id: str = "default",
    idempotency_key: str | None = None,
    audit_sink: AuditSink | None = None,
    metrics: PhaseOneMetrics | None = None,
) -> ClassificationResult:
    """Invoke a lifecycle-owned Phase 1 chain with request-scoped telemetry."""
    resolved_request_id = request_id or str(uuid4())
    config: RunnableConfig = {
        "run_name": "phase_one_request",
        "tags": ["phase-1", "classification"],
        "metadata": {
            "request_id": resolved_request_id,
            "pipeline_version": "phase-1-v1",
        },
    }
    started = perf_counter()
    resolved_metrics = metrics or PhaseOneMetrics(NoOpMetricSink())
    resolved_audit = audit_sink or NoOpAuditSink()
    resolved_metrics.request_started()
    logger.info(
        "phase1.request.started",
        extra={"request_id": resolved_request_id, "pipeline_version": "phase-1-v1"},
    )
    try:
        with request_logging_context(resolved_request_id):
            output = chain.invoke(
                {
                    "message": message,
                    "request_id": resolved_request_id,
                    "tenant_id": tenant_id,
                    "idempotency_key": idempotency_key,
                },
                config=config,
            )
    except (InputSafetyRejection, InputSafetyEscalation):
        logger.warning(
            "phase1.request.rejected",
            extra={
                "request_id": resolved_request_id,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        duration_seconds = perf_counter() - started
        resolved_metrics.request_finished(
            status="rejected", duration_seconds=duration_seconds
        )
        resolved_audit.record(
            AuditEvent(
                event_type="phase1.request.finished",
                request_id=resolved_request_id,
                outcome="rejected",
                metadata={"duration_ms": round(duration_seconds * 1000, 2)},
            )
        )
        raise
    except Exception as exc:
        logger.exception(
            "phase1.request.failed",
            extra={
                "request_id": resolved_request_id,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        duration_seconds = perf_counter() - started
        resolved_metrics.request_finished(
            status="failed", duration_seconds=duration_seconds
        )
        resolved_audit.record(
            AuditEvent(
                event_type="phase1.request.finished",
                request_id=resolved_request_id,
                outcome="failed",
                metadata={
                    "duration_ms": round(duration_seconds * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
        )
        raise
    logger.info(
        "phase1.request.completed",
        extra={
            "request_id": resolved_request_id,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
        },
    )
    duration_seconds = perf_counter() - started
    resolved_metrics.request_finished(
        status="completed", duration_seconds=duration_seconds
    )
    resolved_audit.record(
        AuditEvent(
            event_type="phase1.request.finished",
            request_id=resolved_request_id,
            outcome="completed",
            metadata={"duration_ms": round(duration_seconds * 1000, 2)},
        )
    )
    return output["classification"]
