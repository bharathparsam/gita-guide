from __future__ import annotations

import re
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import APIKeyHeader
from starlette.concurrency import run_in_threadpool

from app.api.config import ApiSettings, load_api_settings
from app.api.middleware import RequestBoundaryMiddleware
from app.api.models import (
    ClassificationRequest,
    ClassificationResponse,
    ConversationSummaryRequest,
    ConversationSummaryResponse,
    ErrorResponse,
    GuidanceApiResponse,
    GuidanceRequest,
    HealthResponse,
)
from app.api.service import PhaseOneService, build_phase_one_service
from app.cache import IdempotencyConflict
from app.classifiers.jev_classifier import ClassificationError
from app.guardrails.input_safety import (
    GuardrailUnavailableError,
    InputSafetyEscalation,
    InputSafetyRejection,
)
from app.observability.logging import configure_logging, get_logger
from app.services.classification_execution import IdempotencyInProgressError
from app.retrieval.nvidia_embeddings import NvidiaEmbeddingError
from app.retrieval.jev_relevance_validator import RetrievalValidationError
from app.services.retrieval_service import (
    AmbiguousVerseReference,
    RetrievalNotEligible,
    VerseReferenceNotFound,
)
from app.services.generation_service import (
    AnswerGroundingError,
    AnswerHelpfulnessError,
    GenerationError,
    GenerationNotReadyError,
    GenerationProviderUnavailableError,
)
from app.services.conversation_service import ConversationSummarizationError


logger = get_logger("api")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


def _request_id(request: Request) -> str:
    return request.state.request_id


def _error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    response_headers = {"X-Request-ID": request_id}
    if headers:
        response_headers.update(headers)
    log_fields = {
        "request_id": request_id,
        "client_request_id": getattr(request.state, "client_request_id", None),
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status_code": status_code,
        "error_code": code,
        "error_stage": details.get("stage") if details else None,
        "failed_dimensions": details.get("failed_dimensions") if details else None,
        "retryable": status_code >= 500 or "Retry-After" in response_headers,
    }
    if status_code >= 500:
        logger.error("api.request.failed", extra=log_fields)
    else:
        logger.warning("api.request.rejected", extra=log_fields)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
                **({"details": details} if details is not None else {}),
            }
        },
        headers=response_headers,
    )


def get_phase_one_service(request: Request) -> PhaseOneService:
    service = getattr(request.app.state, "phase_one_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Service is not ready")
    return service


async def authenticate_api_key(
    request: Request,
    supplied_key: str | None = Depends(api_key_header),
) -> None:
    expected_key: str | None = request.app.state.api_settings.api_key
    if expected_key is None:
        return
    if supplied_key is None or not secrets.compare_digest(supplied_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid API key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )


def create_app(
    *,
    service_factory: Callable[[], PhaseOneService] | None = None,
    api_settings: ApiSettings | None = None,
) -> FastAPI:
    resolved_factory = service_factory or build_phase_one_service
    startup_configuration_error: Exception | None = None
    if api_settings is not None:
        resolved_api_settings = api_settings
    else:
        try:
            resolved_api_settings = load_api_settings()
        except Exception as exc:
            # Keep liveness available for deployment diagnosis, but use an
            # unguessable boundary key and never initialize the guidance service.
            startup_configuration_error = exc
            resolved_api_settings = ApiSettings(api_key=secrets.token_urlsafe(32))

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        service: PhaseOneService | None = None
        application.state.phase_one_service = None
        application.state.startup_error_stage = None
        application.state.startup_error_type = None
        application.state.startup_error_message = None
        try:
            if startup_configuration_error is not None:
                application.state.startup_error_stage = "load_api_settings"
                application.state.startup_error_type = type(
                    startup_configuration_error
                ).__name__
                application.state.startup_error_message = str(
                    startup_configuration_error
                )
                logger.error(
                    "application.configuration.failed",
                    extra={
                        "stage": "load_api_settings",
                        "error_type": type(startup_configuration_error).__name__,
                    },
                    exc_info=(
                        type(startup_configuration_error),
                        startup_configuration_error,
                        startup_configuration_error.__traceback__,
                    ),
                )
            else:
                try:
                    service = resolved_factory()
                except Exception as exc:
                    application.state.startup_error_stage = (
                        "initialize_phase_one_service"
                    )
                    application.state.startup_error_type = type(exc).__name__
                    if isinstance(exc, ValueError):
                        application.state.startup_error_message = str(exc)
                    logger.exception(
                        "application.startup.failed",
                        extra={
                            "stage": "initialize_phase_one_service",
                            "error_type": type(exc).__name__,
                        },
                    )
                else:
                    application.state.phase_one_service = service
            yield
        finally:
            if service is not None:
                service.close()
            application.state.phase_one_service = None

    application = FastAPI(
        title="Gita Guide API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.api_settings = resolved_api_settings
    application.add_middleware(
        RequestBoundaryMiddleware,
        max_request_body_bytes=resolved_api_settings.max_request_body_bytes,
    )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info(
            "http.request.validation_failed",
            extra={
                "request_id": _request_id(request),
                "validation_error_count": len(exc.errors()),
            },
        )
        return _error(
            request,
            status_code=422,
            code="validation_error",
            message="The request payload is invalid.",
        )

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = "unauthorized" if exc.status_code == 401 else "request_failed"
        return _error(
            request,
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
            headers=exc.headers,
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "http.request.unhandled_error",
            extra={"request_id": _request_id(request)},
        )
        return _error(
            request,
            status_code=500,
            code="internal_error",
            message="An unexpected error occurred.",
        )

    @application.get("/health/live", response_model=HealthResponse, tags=["health"])
    async def liveness() -> HealthResponse:
        return HealthResponse(status="ok")

    @application.get(
        "/health/ready",
        response_model=HealthResponse,
        responses={503: {"model": ErrorResponse}},
        tags=["health"],
    )
    async def readiness(request: Request) -> HealthResponse | JSONResponse:
        service = getattr(request.app.state, "phase_one_service", None)
        if service is None or not service.ready:
            return _error(
                request,
                status_code=503,
                code="not_ready",
                message="The service is not ready to receive requests.",
            )
        return HealthResponse(status="ok")

    @application.get(
        "/health/diagnostics",
        dependencies=[Depends(authenticate_api_key)],
        include_in_schema=False,
    )
    async def health_diagnostics(request: Request) -> JSONResponse:
        service = getattr(request.app.state, "phase_one_service", None)
        if service is not None and service.ready:
            return JSONResponse(content={"status": "ok", "startup_error": None})
        startup_error = {
            "stage": getattr(request.app.state, "startup_error_stage", None),
            "error_type": getattr(request.app.state, "startup_error_type", None),
        }
        message = getattr(request.app.state, "startup_error_message", None)
        if message:
            startup_error["message"] = message
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "startup_error": startup_error},
            headers={"Cache-Control": "private, no-store"},
        )

    @application.get(
        "/metrics",
        include_in_schema=False,
        dependencies=[Depends(authenticate_api_key)],
    )
    async def metrics(service: PhaseOneService = Depends(get_phase_one_service)) -> Response:
        return Response(
            content=service.metrics_payload(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @application.post(
        "/v1/classifications",
        response_model=ClassificationResponse,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["classification"],
    )
    async def classify_message(
        payload: ClassificationRequest,
        request: Request,
        _: None = Depends(authenticate_api_key),
        service: PhaseOneService = Depends(get_phase_one_service),
    ) -> ClassificationResponse | JSONResponse:
        request_id = _request_id(request)
        idempotency_values = request.headers.getlist("idempotency-key")
        if len(idempotency_values) > 1:
            return _error(
                request,
                status_code=400,
                code="invalid_idempotency_key",
                message="Idempotency-Key must occur at most once.",
            )
        idempotency_key = idempotency_values[0] if idempotency_values else None
        if idempotency_key is not None and not _IDEMPOTENCY_KEY.fullmatch(
            idempotency_key
        ):
            return _error(
                request,
                status_code=400,
                code="invalid_idempotency_key",
                message="Idempotency-Key must be 1-128 URL-safe characters.",
            )
        try:
            result = await run_in_threadpool(
                service.classify,
                payload.message,
                request_id=request_id,
                idempotency_key=idempotency_key,
            )
        except InputSafetyEscalation:
            return _error(
                request,
                status_code=422,
                code="safety_escalation",
                message=(
                    "Your safety matters more than a reflection right now. Please contact "
                    "local emergency services or a crisis line, and reach out to someone "
                    "you trust."
                ),
            )
        except InputSafetyRejection:
            return _error(
                request,
                status_code=422,
                code="input_blocked",
                message=(
                    "That request has steered the chariot outside this guide’s safety "
                    "boundaries. Let’s bring it back to the road."
                ),
            )
        except GuardrailUnavailableError:
            return _error(
                request,
                status_code=503,
                code="guardrail_unavailable",
                message="The input safety service is temporarily unavailable.",
            )
        except ClassificationError:
            return _error(
                request,
                status_code=502,
                code="classification_failed",
                message="The classification provider returned an invalid response.",
            )
        except IdempotencyConflict:
            return _error(
                request,
                status_code=409,
                code="idempotency_conflict",
                message="The idempotency key was already used for another request.",
            )
        except IdempotencyInProgressError:
            return _error(
                request,
                status_code=409,
                code="idempotency_in_progress",
                message="An identical request is still being processed.",
                headers={"Retry-After": "1"},
            )
        except ValueError:
            return _error(
                request,
                status_code=422,
                code="invalid_input",
                message="The message is invalid.",
            )

        return ClassificationResponse(
            request_id=request_id,
            client_request_id=request.state.client_request_id,
            classification=result,
        )

    @application.post(
        "/v1/guidance",
        response_model=GuidanceApiResponse,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["guidance"],
    )
    async def generate_guidance(
        payload: GuidanceRequest,
        request: Request,
        _: None = Depends(authenticate_api_key),
        service: PhaseOneService = Depends(get_phase_one_service),
    ) -> GuidanceApiResponse | JSONResponse:
        if not request.app.state.api_settings.guidance_api_enabled:
            return _error(
                request,
                status_code=404,
                code="guidance_not_released",
                message="The grounded guidance endpoint has not passed its release gates.",
            )
        request_id = _request_id(request)
        idempotency_values = request.headers.getlist("idempotency-key")
        if len(idempotency_values) > 1:
            return _error(
                request,
                status_code=400,
                code="invalid_idempotency_key",
                message="Idempotency-Key must occur at most once.",
            )
        idempotency_key = idempotency_values[0] if idempotency_values else None
        if idempotency_key is not None and not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            return _error(
                request,
                status_code=400,
                code="invalid_idempotency_key",
                message="Idempotency-Key must be 1-128 URL-safe characters.",
            )
        try:
            result, memory = await run_in_threadpool(
                service.guide_with_context,
                payload.message,
                conversation_context=payload.conversation,
                request_id=request_id,
                idempotency_key=idempotency_key,
            )
        except InputSafetyEscalation:
            return _error(
                request,
                status_code=422,
                code="safety_escalation",
                message=(
                    "Your safety matters more than a reflection right now. Please contact "
                    "local emergency services or a crisis line, and reach out to someone "
                    "you trust."
                ),
            )
        except InputSafetyRejection:
            return _error(
                request,
                status_code=422,
                code="input_blocked",
                message=(
                    "That request has steered the chariot outside this guide’s safety "
                    "boundaries. Let’s bring it back to the road."
                ),
            )
        except AmbiguousVerseReference:
            return _error(
                request,
                status_code=422,
                code="verse_reference_ambiguous",
                message=(
                    "The Gita has a verse 17 in several chapters. Please include both "
                    "numbers—for example, 2.17 or 17.6."
                ),
            )
        except VerseReferenceNotFound:
            return _error(
                request,
                status_code=422,
                code="verse_reference_not_found",
                message=(
                    "I couldn’t find that chapter-and-verse reference in the verified "
                    "Bhagavad Gita text. Please check the reference and try again."
                ),
            )
        except RetrievalNotEligible:
            return _error(
                request,
                status_code=422,
                code="guidance_not_eligible",
                message=(
                    "I couldn’t find a trustworthy Gita reflection for this request. "
                    "Try rephrasing it around the feeling, choice, or situation involved."
                ),
            )
        except GenerationNotReadyError:
            return _error(
                request,
                status_code=422,
                code="insufficient_evidence",
                message=(
                    "I couldn’t find passages strong enough to ground a trustworthy answer."
                ),
            )
        except (GuardrailUnavailableError,):
            return _error(
                request,
                status_code=503,
                code="safety_service_unavailable",
                message="A required safety service is temporarily unavailable.",
            )
        except AnswerHelpfulnessError as exc:
            validation = exc.validation
            details = {
                "stage": "answer_validation",
                "failed_dimensions": list(validation.failed_dimensions),
                "scores": {
                    "faithfulness": validation.faithfulness_probability,
                    "citation_coverage": validation.citation_coverage_probability,
                    "helpfulness": validation.helpfulness_probability,
                    "agency": validation.agency_probability,
                },
                "fallback_trait": exc.trait_id,
            }
            return _error(
                request,
                status_code=422,
                code="guidance_not_helpful",
                message="Live guidance was safe but did not meet the helpfulness target.",
                details=details,
            )
        except AnswerGroundingError as exc:
            validation = exc.validation
            details = None
            if resolved_api_settings.environment != "production" and validation is not None:
                details = {
                    "stage": "answer_validation",
                    "failed_dimensions": list(validation.failed_dimensions),
                    "scores": {
                        "faithfulness": validation.faithfulness_probability,
                        "citation_coverage": validation.citation_coverage_probability,
                        "helpfulness": validation.helpfulness_probability,
                        "agency": validation.agency_probability,
                    },
                }
            return _error(
                request,
                status_code=502,
                code="guidance_failed",
                message="Grounded guidance did not pass the final quality check.",
                details=details,
            )
        except GenerationProviderUnavailableError:
            return _error(
                request,
                status_code=503,
                code="generation_service_unavailable",
                message="The guidance provider is temporarily unavailable. Please try again shortly.",
                headers={"Retry-After": "2"},
            )
        except (ClassificationError, NvidiaEmbeddingError, RetrievalValidationError, GenerationError):
            return _error(
                request,
                status_code=502,
                code="guidance_failed",
                message="Grounded guidance could not be produced safely.",
            )
        except IdempotencyConflict:
            return _error(
                request,
                status_code=409,
                code="idempotency_conflict",
                message="The idempotency key was already used for another request.",
            )
        except IdempotencyInProgressError:
            return _error(
                request,
                status_code=409,
                code="idempotency_in_progress",
                message="An identical request is still being processed.",
                headers={"Retry-After": "1"},
            )
        return GuidanceApiResponse(
            request_id=request_id,
            client_request_id=request.state.client_request_id,
            result=result,
            conversation=memory.context,
            summary_updated=memory.summary_updated,
            summary_deferred=memory.summary_deferred,
            summarized_turn_count=memory.summarized_turn_count,
        )

    @application.post(
        "/v1/conversations/summarize",
        response_model=ConversationSummaryResponse,
        responses={
            401: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
        },
        tags=["conversation"],
    )
    async def summarize_conversation(
        payload: ConversationSummaryRequest,
        request: Request,
        _: None = Depends(authenticate_api_key),
        service: PhaseOneService = Depends(get_phase_one_service),
    ) -> ConversationSummaryResponse | JSONResponse:
        request_id = _request_id(request)
        try:
            memory = await run_in_threadpool(
                service.summarize_conversation,
                payload.conversation,
                request_id=request_id,
            )
        except ConversationSummarizationError:
            return _error(
                request,
                status_code=502,
                code="conversation_summarization_failed",
                message="Conversation memory could not be summarized.",
            )
        return ConversationSummaryResponse(
            request_id=request_id,
            client_request_id=request.state.client_request_id,
            conversation=memory.context,
            summary_updated=memory.summary_updated,
            summarized_turn_count=memory.summarized_turn_count,
        )

    return application


app = create_app()
