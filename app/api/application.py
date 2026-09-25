from __future__ import annotations

import re
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

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
    ErrorResponse,
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
) -> JSONResponse:
    request_id = _request_id(request)
    response_headers = {"X-Request-ID": request_id}
    if headers:
        response_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
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
    resolved_api_settings = api_settings or load_api_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        service = resolved_factory()
        application.state.phase_one_service = service
        try:
            yield
        finally:
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
                    "This message requires immediate safety support and was not "
                    "sent for classification."
                ),
            )
        except InputSafetyRejection:
            return _error(
                request,
                status_code=422,
                code="input_blocked",
                message="This message cannot be processed under the input safety policy.",
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

    return application


app = create_app()
