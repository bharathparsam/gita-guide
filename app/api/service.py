from __future__ import annotations

import secrets
from threading import Lock, local
from typing import Protocol

import requests
from langchain_core.runnables import Runnable
from redis import Redis
from upstash_redis import Redis as UpstashRedis

from app.cache import (
    ClassificationCache,
    ClassificationCacheKeyContext,
    ClassificationCachePolicy,
    HmacCacheKeyBuilder,
    IdempotencyStore,
    InMemoryCacheBackend,
    RedisCacheBackend,
    SingleFlight,
    UpstashRedisCacheBackend,
)
from app.classifiers.jev_classifier import JEV_PROMPT_VERSION, JevClassifier
from app.classifiers.taxonomy import TAXONOMY_VERSION
from app.config import Settings, get_settings
from app.guardrails.input_safety import (
    CompositeInputGuardrail,
    LexicalInputGuardrail,
    NvidiaSafetyGuardrail,
)
from app.models.classification import ClassificationResult
from app.observability.audit import JsonlAuditSink, NoOpAuditSink
from app.observability.metrics import PhaseOneMetrics
from app.observability.prometheus import PrometheusMetricSink
from app.services.classification_execution import ClassificationExecutor
from app.services.classification_service import (
    PhaseOneState,
    build_phase_one_chain,
    invoke_phase_one_chain,
)


class PhaseOneService(Protocol):
    @property
    def ready(self) -> bool: ...

    def classify(
        self,
        message: str,
        *,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> ClassificationResult: ...

    def metrics_payload(self) -> bytes: ...

    def close(self) -> None: ...


class ManagedPhaseOneService:
    """Lifecycle-owned adapter around the synchronous Phase 1 pipeline.

    A requests session is reused per worker thread. ``requests.Session`` is not
    documented as thread-safe, so a single global session is deliberately not
    shared across FastAPI's thread pool.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._local = local()
        self._sessions: list[requests.Session] = []
        self._lock = Lock()
        self._closed = False
        self._redis_client: Redis | None = None
        self._upstash_client: UpstashRedis | None = None
        self._single_flight = SingleFlight()
        self._metric_sink = PrometheusMetricSink()
        self._metrics = PhaseOneMetrics(self._metric_sink)
        self._audit_sink = (
            JsonlAuditSink(settings.audit_log_path, create_parents=True)
            if settings.audit_log_path
            else NoOpAuditSink()
        )

        cache_secret = settings.cache_hmac_secret or secrets.token_urlsafe(32)
        key_builder = HmacCacheKeyBuilder(cache_secret)
        if settings.cache_backend == "redis":
            assert settings.redis_url is not None
            self._redis_client = Redis.from_url(settings.redis_url)
            self._redis_client.ping()
            backend = RedisCacheBackend(self._redis_client)
        elif settings.cache_backend == "upstash":
            assert settings.upstash_redis_rest_url is not None
            assert settings.upstash_redis_rest_token is not None
            self._upstash_client = UpstashRedis(
                url=settings.upstash_redis_rest_url,
                token=settings.upstash_redis_rest_token,
                allow_telemetry=False,
            )
            self._upstash_client.ping()
            backend = UpstashRedisCacheBackend(self._upstash_client)
        elif settings.cache_backend == "memory":
            backend = InMemoryCacheBackend()
        else:
            backend = None

        if backend is None:
            self._classification_cache = None
            self._idempotency_store = None
            self._cache_context = None
        else:
            self._classification_cache = ClassificationCache(
                backend,
                key_builder,
                policy=ClassificationCachePolicy(
                    ttl_seconds=settings.classification_cache_ttl_seconds,
                    minimum_confidence=settings.classification_min_confidence,
                ),
            )
            self._idempotency_store = IdempotencyStore(
                backend,
                key_builder,
                ttl_seconds=settings.idempotency_ttl_seconds,
            )
            self._cache_context = ClassificationCacheKeyContext(
                tenant_id=settings.cache_tenant_id,
                model_version=settings.openrouter_model,
                taxonomy_version=TAXONOMY_VERSION,
                prompt_version=JEV_PROMPT_VERSION,
                confidence_threshold=settings.classification_min_confidence,
                scope_threshold=settings.classification_scope_threshold,
            )

    @property
    def ready(self) -> bool:
        return not self._closed

    def _dependencies(
        self,
    ) -> Runnable[PhaseOneState, PhaseOneState]:
        if self._closed:
            raise RuntimeError("Phase One service is closed")

        chain = getattr(self._local, "chain", None)
        if chain is not None:
            return chain

        jev_session = requests.Session()
        nvidia_session = requests.Session()
        with self._lock:
            if self._closed:
                jev_session.close()
                nvidia_session.close()
                raise RuntimeError("Phase One service is closed")
            self._sessions.extend((jev_session, nvidia_session))

        classifier = JevClassifier(
            self._settings,
            session=jev_session,
            metrics=self._metrics,
        ).classify
        executor = ClassificationExecutor(
            classifier,
            cache=self._classification_cache,
            cache_context=self._cache_context,
            idempotency_store=self._idempotency_store,
            single_flight=self._single_flight,
        )
        guardrail = CompositeInputGuardrail(
            (
                LexicalInputGuardrail(),
                NvidiaSafetyGuardrail(
                    self._settings,
                    session=nvidia_session,
                    metrics=self._metrics,
                ),
            )
        )
        chain = build_phase_one_chain(
            guardrail=guardrail,
            classification_executor=executor,
            audit_sink=self._audit_sink,
            metrics=self._metrics,
        )
        self._local.chain = chain
        return chain

    def classify(
        self,
        message: str,
        *,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> ClassificationResult:
        chain = self._dependencies()
        return invoke_phase_one_chain(
            chain,
            message,
            request_id=request_id,
            tenant_id=self._settings.cache_tenant_id,
            idempotency_key=idempotency_key,
            audit_sink=self._audit_sink,
            metrics=self._metrics,
        )

    def metrics_payload(self) -> bytes:
        return self._metric_sink.render()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            sessions, self._sessions = self._sessions, []
        for session in sessions:
            session.close()
        if self._redis_client is not None:
            self._redis_client.close()
        if self._upstash_client is not None:
            self._upstash_client.close()


def build_phase_one_service() -> ManagedPhaseOneService:
    return ManagedPhaseOneService(get_settings())
