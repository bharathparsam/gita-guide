from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from fastapi.testclient import TestClient

from app.api.application import create_app
from app.api.config import ApiSettings
from app.models.classification import ClassificationResult


class LoadService:
    ready = True

    def __init__(self) -> None:
        self.calls = 0
        self.lock = Lock()

    def classify(self, message, *, request_id, idempotency_key=None):
        with self.lock:
            self.calls += 1
        return ClassificationResult(
            in_scope=True,
            in_scope_probability=0.95,
            primary_situation="outcome_anxiety",
            primary_situation_confidence=0.9,
            primary_emotion="fear",
            primary_emotion_confidence=0.9,
            root_conflict="uncertainty",
            root_conflict_confidence=0.9,
        )

    def metrics_payload(self):
        return b""

    def close(self):
        self.ready = False


def test_http_boundary_handles_one_hundred_concurrent_requests() -> None:
    service = LoadService()
    application = create_app(
        service_factory=lambda: service,
        api_settings=ApiSettings(api_key="load-secret", environment="test"),
    )
    with TestClient(application) as client:
        def invoke(index: int):
            return client.post(
                "/v1/classifications",
                json={"message": "I am anxious about the result"},
                headers={
                    "X-API-Key": "load-secret",
                    "Idempotency-Key": f"load-{index}",
                },
            )

        with ThreadPoolExecutor(max_workers=16) as pool:
            responses = list(pool.map(invoke, range(100)))

    assert all(response.status_code == 200 for response in responses)
    request_ids = {response.headers["X-Request-ID"] for response in responses}
    assert len(request_ids) == 100
    assert service.calls == 100
