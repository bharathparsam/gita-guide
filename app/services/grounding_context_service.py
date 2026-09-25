from __future__ import annotations

from time import perf_counter
from typing import cast

from langchain_core.runnables import Runnable, RunnableConfig

from app.guardrails.input_safety import InputSafetyEscalation, InputSafetyRejection
from app.models.retrieval import GroundingContext
from app.observability.audit import AuditEvent, AuditSink, NoOpAuditSink
from app.observability.logging import get_logger, request_logging_context
from app.observability.metrics import NoOpMetricSink, PhaseOneMetrics
from app.services.classification_service import PhaseOneState
from app.services.retrieval_service import RetrievalState


GROUNDING_CONTEXT_PIPELINE_VERSION = "grounding-context-v1"
logger = get_logger("grounding_context")


def invoke_grounding_context_chain(
    phase_one_chain: Runnable[PhaseOneState, PhaseOneState],
    retrieval_chain: Runnable[RetrievalState, RetrievalState],
    message: str,
    *,
    request_id: str,
    tenant_id: str = "default",
    idempotency_key: str | None = None,
    audit_sink: AuditSink | None = None,
    metrics: PhaseOneMetrics | None = None,
) -> GroundingContext:
    """Run classification and retrieval beneath one correlated LangSmith root."""
    resolved_audit = audit_sink or NoOpAuditSink()
    resolved_metrics = metrics or PhaseOneMetrics(NoOpMetricSink())
    chain = phase_one_chain | cast(Runnable[PhaseOneState, PhaseOneState], retrieval_chain)
    config: RunnableConfig = {
        "run_name": "gita_guide_grounding_context_request",
        "tags": ["phase-1", "phase-2", "grounding-context"],
        "metadata": {
            "request_id": request_id,
            "pipeline_version": GROUNDING_CONTEXT_PIPELINE_VERSION,
        },
    }
    started = perf_counter()
    status = "failed"
    resolved_metrics.request_started()
    logger.info(
        "grounding_context.request.started",
        extra={
            "request_id": request_id,
            "pipeline_version": GROUNDING_CONTEXT_PIPELINE_VERSION,
        },
    )
    try:
        with request_logging_context(request_id):
            output = chain.invoke(
                {
                    "message": message,
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                    "idempotency_key": idempotency_key,
                },
                config=config,
            )
    except (InputSafetyRejection, InputSafetyEscalation):
        status = "rejected"
        raise
    except Exception:
        status = "failed"
        logger.exception(
            "grounding_context.request.failed",
            extra={"request_id": request_id},
        )
        raise
    else:
        status = "completed"
        return GroundingContext(
            request_id=request_id,
            classification=output["classification"],
            retrieval=output["retrieval"],
        )
    finally:
        duration_seconds = perf_counter() - started
        resolved_metrics.request_finished(
            status=status,
            duration_seconds=duration_seconds,
        )
        resolved_audit.record(
            AuditEvent(
                event_type="grounding_context.request.finished",
                request_id=request_id,
                outcome=status,
                metadata={
                    "pipeline_version": GROUNDING_CONTEXT_PIPELINE_VERSION,
                    "duration_ms": round(duration_seconds * 1000, 2),
                },
            )
        )
        logger.info(
            "grounding_context.request.finished",
            extra={
                "request_id": request_id,
                "status": status,
                "duration_ms": round(duration_seconds * 1000, 2),
            },
        )
