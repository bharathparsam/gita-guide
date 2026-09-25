from __future__ import annotations

import secrets
from threading import Lock, local
from typing import Protocol

import requests
from langchain_core.runnables import Runnable
from redis import Redis
from upstash_redis import Redis as UpstashRedis
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from app.cache import (
    ClassificationCache,
    ClassificationCacheKeyContext,
    ClassificationCachePolicy,
    HmacCacheKeyBuilder,
    IdempotencyStore,
    InMemoryCacheBackend,
    RedisCacheBackend,
    RetrievalCache,
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
from app.models.retrieval import GroundingContext, RetrievalResult
from app.models.generation import GuidanceResponse
from app.observability.audit import JsonlAuditSink, NoOpAuditSink
from app.observability.metrics import PhaseOneMetrics
from app.observability.prometheus import PrometheusMetricSink
from app.services.classification_execution import ClassificationExecutor
from app.services.classification_service import (
    PhaseOneState,
    build_phase_one_chain,
    invoke_phase_one_chain,
)
from app.retrieval.local_retriever import (
    DEFAULT_CHUNKS_PATH,
    DEFAULT_EMBEDDINGS_PATH,
    DEFAULT_METADATA_PATH,
)
from app.retrieval.gita_vector_retriever import GitaVectorRetriever
from app.retrieval.nvidia_embeddings import NvidiaNemotronEmbeddings
from app.retrieval.jev_relevance_validator import JevRetrievalValidator
from app.services.retrieval_service import (
    RetrievalExecutor,
    RetrievalPolicy,
    RetrievalState,
    build_filtered_retrieval_chain,
    invoke_retrieval_chain,
)
from app.services.grounding_context_service import invoke_grounding_context_chain
from app.services.generation_service import (
    GroundedGuidanceGenerator,
    build_grounded_generation_input,
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

    def retrieve_context(
        self,
        message: str,
        classification: ClassificationResult,
        *,
        request_id: str,
    ) -> RetrievalResult: ...

    def classify_and_retrieve(
        self,
        message: str,
        *,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> GroundingContext: ...

    def guide(
        self,
        message: str,
        *,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> GuidanceResponse: ...

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

        self._retrieval_cache = (
            RetrievalCache(
                backend,
                key_builder,
                ttl_seconds=settings.retrieval_cache_ttl_seconds,
            )
            if backend is not None
            else None
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

    def _retrieval_dependencies(self) -> Runnable[RetrievalState, RetrievalState]:
        if self._closed:
            raise RuntimeError("Phase One service is closed")
        chain = getattr(self._local, "retrieval_chain", None)
        if chain is not None:
            return chain

        embedding_session = requests.Session()
        validation_session = requests.Session()
        with self._lock:
            if self._closed:
                embedding_session.close()
                validation_session.close()
                raise RuntimeError("Phase One service is closed")
            self._sessions.extend((embedding_session, validation_session))

        embeddings = NvidiaNemotronEmbeddings.from_environment(
            session=embedding_session,
            metrics=self._metrics,
        )
        retriever = GitaVectorRetriever.from_files(
            chunks_path=DEFAULT_CHUNKS_PATH,
            embeddings_path=DEFAULT_EMBEDDINGS_PATH,
            metadata_path=DEFAULT_METADATA_PATH,
            embeddings=embeddings,
        )
        executor = RetrievalExecutor(
            retriever,
            JevRetrievalValidator(
                self._settings,
                threshold=self._settings.retrieval_validation_threshold,
                session=validation_session,
                metrics=self._metrics,
            ),
            tenant_id=self._settings.cache_tenant_id,
            policy=RetrievalPolicy(
                candidate_k=self._settings.retrieval_candidate_k,
                top_k=self._settings.retrieval_top_k,
                minimum_score=self._settings.retrieval_minimum_score,
                mmr_lambda=self._settings.retrieval_mmr_lambda,
                max_per_chapter=self._settings.retrieval_max_per_chapter,
            ),
            cache=self._retrieval_cache,
            single_flight=self._single_flight,
            audit_sink=self._audit_sink,
            metrics=self._metrics,
        )
        chain = build_filtered_retrieval_chain(executor)
        self._local.retrieval_chain = chain
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

    def retrieve_context(
        self,
        message: str,
        classification: ClassificationResult,
        *,
        request_id: str,
    ) -> RetrievalResult:
        return invoke_retrieval_chain(
            self._retrieval_dependencies(),
            message=message,
            classification=classification,
            request_id=request_id,
            tenant_id=self._settings.cache_tenant_id,
        )

    def classify_and_retrieve(
        self,
        message: str,
        *,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> GroundingContext:
        return invoke_grounding_context_chain(
            self._dependencies(),
            self._retrieval_dependencies(),
            message,
            request_id=request_id,
            tenant_id=self._settings.cache_tenant_id,
            idempotency_key=idempotency_key,
            audit_sink=self._audit_sink,
            metrics=self._metrics,
        )

    def _generation_dependencies(self) -> GroundedGuidanceGenerator:
        if self._closed:
            raise RuntimeError("Gita Guide service is closed")
        generator = getattr(self._local, "guidance_generator", None)
        if generator is not None:
            return generator

        output_guardrail_session = requests.Session()
        with self._lock:
            if self._closed:
                output_guardrail_session.close()
                raise RuntimeError("Gita Guide service is closed")
            self._sessions.append(output_guardrail_session)
        output_guardrail = NvidiaSafetyGuardrail(
            self._settings,
            session=output_guardrail_session,
            metrics=self._metrics,
        )
        model = ChatNVIDIA(
            model=self._settings.nvidia_generation_model,
            nvidia_api_key=self._settings.nvidia_guardrail_api_key,
            base_url=self._settings.nvidia_generation_url,
            temperature=self._settings.nvidia_generation_temperature,
            max_completion_tokens=self._settings.nvidia_generation_max_tokens,
            top_p=0.9,
            model_kwargs={
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        generator = GroundedGuidanceGenerator(
            model,
            model_name=self._settings.nvidia_generation_model,
            output_guardrail=output_guardrail.check_output,
            audit_sink=self._audit_sink,
            metrics=self._metrics,
        )
        self._local.guidance_generator = generator
        return generator

    def guide(
        self,
        message: str,
        *,
        request_id: str,
        idempotency_key: str | None = None,
    ) -> GuidanceResponse:
        context = self.classify_and_retrieve(
            message,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )
        generation_input = build_grounded_generation_input(message, context)
        return self._generation_dependencies().generate(generation_input)

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
