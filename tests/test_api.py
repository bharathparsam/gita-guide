from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.api.application import create_app
from app.api.config import ApiSettings
from app.guardrails.grounding import AnswerValidation
from app.models.classification import ClassificationResult
from app.models.conversation import ConversationContext, ConversationMemoryUpdate
from app.models.generation import GuidancePresentation, GuidanceResponse
from app.services.generation_service import AnswerGroundingError
from app.services.generation_service import AnswerHelpfulnessError
from app.services.generation_service import GenerationProviderUnavailableError


def classification_result() -> ClassificationResult:
    return ClassificationResult(
        in_scope=True,
        in_scope_probability=0.91,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.88,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="attachment_to_results",
        root_conflict_confidence=0.86,
        provider_request_id="provider-123",
        model="test-jev",
    )


class FakePhaseOneService:
    def __init__(self) -> None:
        self.ready = True
        self.closed = False
        self.calls: list[tuple[str, str]] = []
        self.idempotency_keys: list[str | None] = []

    def classify(
        self,
        message: str,
        *,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> ClassificationResult:
        self.calls.append((message, request_id))
        self.idempotency_keys.append(idempotency_key)
        return classification_result()

    def metrics_payload(self) -> bytes:
        return b"gita_guide_test_total 1\n"

    def guide(
        self,
        message: str,
        *,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> GuidanceResponse:
        self.calls.append((message, request_id))
        self.idempotency_keys.append(idempotency_key)
        return GuidanceResponse(
            request_id=request_id,
            guidance=(
                "What Krishna said\nFocus on your effort [Bhagavad Gita 2.47].\n\n"
                "How to overcome\nChoose one available action."
            ),
            presentation=GuidancePresentation(
                trait_id="result_obsession",
                label="Result Obsession",
                what_krishna_said="Focus on your effort [Bhagavad Gita 2.47].",
                how_to_overcome="Choose one available action.",
                verse="2.47",
                sloka=(
                    "karmaṇy evādhikāras te\n"
                    "mā phaleṣu kadācana\n"
                    "mā karma-phala-hetur bhūr\n"
                    "mā te saṅgo ’stv akarmaṇi"
                ),
            ),
            citations=("Bhagavad Gita 2.47",),
            grounded_chunk_ids=("gita:2:47",),
            model="test-generator",
            validation_model="test-judge",
            faithfulness_probability=0.95,
            citation_coverage_probability=0.96,
            helpfulness_probability=0.91,
            agency_probability=0.99,
        )

    def guide_with_context(
        self,
        message: str,
        *,
        conversation_context: ConversationContext,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> tuple[GuidanceResponse, ConversationMemoryUpdate]:
        result = self.guide(
            message,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        memory = ConversationMemoryUpdate(
            context=ConversationContext(
                summary=conversation_context.summary,
                recent_turns=(
                    *conversation_context.recent_turns,
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": result.guidance},
                ),
            ),
            summary_updated=False,
        )
        return result, memory

    def summarize_conversation(
        self,
        conversation_context: ConversationContext,
        *,
        request_id: str,
    ) -> ConversationMemoryUpdate:
        return ConversationMemoryUpdate(
            context=conversation_context,
            summary_updated=False,
        )

    def close(self) -> None:
        self.ready = False
        self.closed = True


class RejectingGuidanceService(FakePhaseOneService):
    def guide_with_context(
        self,
        message: str,
        *,
        conversation_context: ConversationContext,
        request_id: str,
        idempotency_key: str | None = None,
    ):
        raise AnswerGroundingError(
            "Generated guidance failed semantic grounding validation",
            validation=AnswerValidation(
                faithfulness_probability=0.87,
                citation_coverage_probability=0.92,
                helpfulness_probability=0.78,
                agency_probability=0.76,
                accepted=False,
                model="test-answer-judge",
                provider_request_id="answer-rejected-1",
                failed_dimensions=("agency",),
            ),
        )


class UnhelpfulGuidanceService(FakePhaseOneService):
    def guide_with_context(
        self,
        message: str,
        *,
        conversation_context: ConversationContext,
        request_id: str,
        idempotency_key: str | None = None,
    ):
        raise AnswerHelpfulnessError(
            "Generated guidance did not meet the helpfulness target",
            trait_id="purpose",
            validation=AnswerValidation(
                faithfulness_probability=0.9,
                citation_coverage_probability=0.92,
                helpfulness_probability=0.64,
                agency_probability=0.9,
                accepted=False,
                model="test-answer-judge",
                provider_request_id="answer-unhelpful-1",
                failed_dimensions=("helpfulness",),
            ),
        )


class UnavailableGuidanceService(FakePhaseOneService):
    def guide_with_context(
        self,
        message: str,
        *,
        conversation_context: ConversationContext,
        request_id: str,
        idempotency_key: str | None = None,
    ):
        raise GenerationProviderUnavailableError("openrouter unavailable")


def test_classification_uses_server_request_id_and_preserves_client_id() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key="secret"),
    )

    with TestClient(application) as client:
        response = client.post(
            "/v1/classifications",
            json={"message": "I am anxious about my exam result"},
            headers={
                "X-API-Key": "secret",
                "X-Request-ID": "untrusted-request-id",
                "X-Client-Request-ID": "mobile-123",
            },
        )

    assert response.status_code == 200
    body = response.json()
    UUID(body["request_id"])
    assert body["request_id"] != "untrusted-request-id"
    assert response.headers["X-Request-ID"] == body["request_id"]
    assert body["client_request_id"] == "mobile-123"
    assert service.calls == [
        ("I am anxious about my exam result", body["request_id"])
    ]
    assert service.closed is True


def test_classification_requires_configured_api_key() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key="secret"),
    )

    with TestClient(application) as client:
        response = client.post(
            "/v1/classifications",
            json={"message": "I feel confused"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]
    assert service.calls == []


def test_invalid_client_request_id_is_rejected() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key=None),
    )

    with TestClient(application) as client:
        response = client.post(
            "/v1/classifications",
            json={"message": "I feel confused"},
            headers={"X-Client-Request-ID": "contains spaces"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_client_request_id"
    assert service.calls == []


def test_request_body_limit_is_enforced_before_json_parsing() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key=None, max_request_body_bytes=32),
    )

    with TestClient(application) as client:
        response = client.post(
            "/v1/classifications",
            content=b'{"message":"' + (b"a" * 100) + b'"}',
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
    assert service.calls == []


def test_validation_errors_do_not_echo_the_user_message() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key=None),
    )
    sensitive_text = "private-message-that-must-not-be-returned"

    with TestClient(application) as client:
        response = client.post(
            "/v1/classifications",
            json={"message": sensitive_text, "unexpected": sensitive_text},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert sensitive_text not in response.text
    assert service.calls == []


def test_health_endpoints_are_public() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key="secret"),
    )

    with TestClient(application) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok"}
    assert "X-Request-ID" in live.headers
    assert "X-Request-ID" in ready.headers


def test_liveness_survives_service_startup_failure_and_readiness_fails_closed() -> None:
    def fail_to_start() -> FakePhaseOneService:
        raise RuntimeError("dependency initialization failed")

    application = create_app(
        service_factory=fail_to_start,
        api_settings=ApiSettings(api_key="secret"),
    )

    with TestClient(application) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 503
    assert ready.json()["error"]["code"] == "not_ready"
    assert application.state.startup_error_type == "RuntimeError"


def test_authenticated_diagnostics_exposes_safe_configuration_failure() -> None:
    def fail_to_start() -> FakePhaseOneService:
        raise ValueError("CACHE_HMAC_SECRET must contain at least 32 bytes")

    application = create_app(
        service_factory=fail_to_start,
        api_settings=ApiSettings(api_key="secret"),
    )

    with TestClient(application) as client:
        unauthorized = client.get("/health/diagnostics")
        diagnostic = client.get(
            "/health/diagnostics",
            headers={"X-API-Key": "secret"},
        )

    assert unauthorized.status_code == 401
    assert diagnostic.status_code == 503
    assert diagnostic.headers["Cache-Control"] == "private, no-store"
    assert diagnostic.json() == {
        "status": "not_ready",
        "startup_error": {
            "stage": "initialize_phase_one_service",
            "error_type": "ValueError",
            "message": "CACHE_HMAC_SECRET must contain at least 32 bytes",
        },
    }


def test_liveness_survives_invalid_production_api_configuration(
    monkeypatch,
) -> None:
    service = FakePhaseOneService()
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.delenv("APP_API_KEY", raising=False)

    application = create_app(service_factory=lambda: service)

    with TestClient(application) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")

    assert live.status_code == 200
    assert ready.status_code == 503
    assert ready.json()["error"]["code"] == "not_ready"
    assert application.state.startup_error_type == "ValueError"
    assert service.closed is False


def test_metrics_requires_authentication_and_returns_prometheus_payload() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key="secret"),
    )

    with TestClient(application) as client:
        unauthorized = client.get("/metrics")
        response = client.get("/metrics", headers={"X-API-Key": "secret"})

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert "gita_guide_test_total 1" in response.text


def test_invalid_idempotency_key_is_rejected_before_service_call() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key=None),
    )

    with TestClient(application) as client:
        response = client.post(
            "/v1/classifications",
            json={"message": "I feel confused"},
            headers={"Idempotency-Key": "contains spaces"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_idempotency_key"
    assert service.calls == []


def test_valid_idempotency_key_is_forwarded_to_phase_one_service() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key=None),
    )

    with TestClient(application) as client:
        response = client.post(
            "/v1/classifications",
            json={"message": "I feel confused"},
            headers={"Idempotency-Key": "mobile-retry-123"},
        )

    assert response.status_code == 200
    assert service.idempotency_keys == ["mobile-retry-123"]


def test_guidance_endpoint_is_hidden_until_release_gates_are_approved() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key=None),
    )
    with TestClient(application) as client:
        response = client.post("/v1/guidance", json={"message": "I feel anxious"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "guidance_not_released"
    assert service.calls == []


def test_released_guidance_endpoint_returns_validated_result() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(
            api_key="secret",
            guidance_api_enabled=True,
            guidance_release_approved=True,
        ),
    )
    with TestClient(application) as client:
        response = client.post(
            "/v1/guidance",
            json={"message": "I feel anxious about the result"},
            headers={"X-API-Key": "secret", "Idempotency-Key": "guide-1"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == body["result"]["request_id"]
    assert body["result"]["faithfulness_probability"] == 0.95
    assert body["result"]["presentation"]["label"] == "Result Obsession"
    assert body["result"]["presentation"]["verse"] == "2.47"
    assert body["conversation"]["recent_turns"][0] == {
        "role": "user",
        "content": "I feel anxious about the result",
    }
    assert body["summary_updated"] is False
    assert service.idempotency_keys == ["guide-1"]


def test_guidance_quality_rejection_has_development_diagnostics() -> None:
    service = RejectingGuidanceService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(
            api_key="secret",
            environment="development",
            guidance_api_enabled=True,
            guidance_release_approved=True,
        ),
    )
    with TestClient(application) as client:
        response = client.post(
            "/v1/guidance",
            json={"message": "I am anxious about the result"},
            headers={"X-API-Key": "secret"},
        )

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["message"] == "Grounded guidance did not pass the final quality check."
    assert error["details"] == {
        "stage": "answer_validation",
        "failed_dimensions": ["agency"],
        "scores": {
            "faithfulness": 0.87,
            "citation_coverage": 0.92,
            "helpfulness": 0.78,
            "agency": 0.76,
        },
    }
    assert response.headers["X-Request-ID"] == error["request_id"]


def test_guidance_quality_rejection_hides_diagnostics_in_production() -> None:
    service = RejectingGuidanceService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(
            api_key="secret",
            environment="production",
            guidance_api_enabled=True,
            guidance_release_approved=True,
        ),
    )
    with TestClient(application) as client:
        response = client.post(
            "/v1/guidance",
            json={"message": "I am anxious about the result"},
            headers={"X-API-Key": "secret"},
        )

    assert response.status_code == 502
    assert "details" not in response.json()["error"]


def test_helpfulness_only_rejection_returns_curated_fallback_signal() -> None:
    application = create_app(
        service_factory=UnhelpfulGuidanceService,
        api_settings=ApiSettings(
            api_key="secret",
            environment="production",
            guidance_api_enabled=True,
            guidance_release_approved=True,
        ),
    )
    with TestClient(application) as client:
        response = client.post(
            "/v1/guidance",
            json={"message": "I feel lost about my path"},
            headers={"X-API-Key": "secret"},
        )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "guidance_not_helpful"
    assert error["details"]["failed_dimensions"] == ["helpfulness"]
    assert error["details"]["fallback_trait"] == "purpose"
    assert error["details"]["scores"]["helpfulness"] == 0.64


def test_generation_provider_outage_is_reported_as_retryable() -> None:
    application = create_app(
        service_factory=UnavailableGuidanceService,
        api_settings=ApiSettings(
            api_key="secret",
            guidance_api_enabled=True,
            guidance_release_approved=True,
        ),
    )

    with TestClient(application) as client:
        response = client.post(
            "/v1/guidance",
            json={"message": "I am anxious about the result"},
            headers={"X-API-Key": "secret"},
        )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
    assert response.json()["error"]["code"] == "generation_service_unavailable"
    assert "temporarily unavailable" in response.json()["error"]["message"]


def test_conversation_summary_endpoint_returns_portable_context() -> None:
    service = FakePhaseOneService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key="secret"),
    )
    payload = {
        "conversation": {
            "summary": "The user is preparing for an interview.",
            "recent_turns": [
                {"role": "user", "content": "I feel nervous."},
                {"role": "assistant", "content": "What feels uncertain?"},
            ],
        }
    }
    with TestClient(application) as client:
        unauthorized = client.post("/v1/conversations/summarize", json=payload)
        response = client.post(
            "/v1/conversations/summarize",
            json=payload,
            headers={"X-API-Key": "secret"},
        )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["conversation"] == {
        "schema_version": "1.0",
        **payload["conversation"],
    }
    assert response.json()["summary_updated"] is False
