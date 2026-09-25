from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.api.application import create_app
from app.api.config import ApiSettings
from app.models.classification import ClassificationResult


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

    def close(self) -> None:
        self.ready = False
        self.closed = True


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
