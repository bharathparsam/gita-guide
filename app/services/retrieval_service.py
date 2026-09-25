from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, time
from typing import Any, TypedDict, cast

from langchain_core.documents import Document
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from app.cache import (
    CachedRetrievalItem,
    RetrievalCache,
    RetrievalCacheKeyContext,
    SingleFlight,
)
from app.models.classification import ClassificationResult
from app.models.retrieval import RetrievedChunk, RetrievalResult
from app.observability.audit import AuditEvent, AuditSink, NoOpAuditSink
from app.observability.logging import get_logger, prompt_log_fields, request_logging_context
from app.observability.metrics import NoOpMetricSink, PhaseOneMetrics
from app.retrieval.gita_vector_retriever import (
    GitaVectorRetriever,
    RetrievalCorpusError,
    build_classification_query,
)
from app.retrieval.jev_relevance_validator import (
    RetrievalValidationError,
    RetrievalValidator,
)


RETRIEVAL_PIPELINE_VERSION = "retrieval-v2"
RERANKER_VERSION = "dense-mmr-v1"
logger = get_logger("retrieval")


class RetrievalNotEligible(ValueError):
    """Raised when Phase 1 does not safely support automated retrieval."""


@dataclass(frozen=True, slots=True)
class RetrievalPolicy:
    candidate_k: int = 20
    top_k: int = 5
    minimum_score: float = 0.0
    mmr_lambda: float = 0.8
    max_per_chapter: int = 2
    allowed_source_ids: tuple[str, ...] = ("gita-swarupananda-1909",)
    allowed_speakers: tuple[str, ...] = ("The Blessed Lord said",)

    def __post_init__(self) -> None:
        if self.candidate_k < 1 or self.top_k < 1 or self.top_k > 5:
            raise ValueError("candidate_k and top_k must be positive and top_k cannot exceed 5")
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be at least top_k")
        if not -1 <= self.minimum_score <= 1:
            raise ValueError("minimum_score must be between -1 and 1")
        if not 0 <= self.mmr_lambda <= 1:
            raise ValueError("mmr_lambda must be between 0 and 1")
        if self.max_per_chapter < 1:
            raise ValueError("max_per_chapter must be positive")
        if not self.allowed_source_ids or not self.allowed_speakers:
            raise ValueError("source and speaker allowlists cannot be empty")


@dataclass(frozen=True, slots=True)
class _Retrieved:
    documents: tuple[Document, ...]
    candidate_count: int
    source: str
    cache_age_seconds: float | None = None
    validation_rejected_count: int = 0
    validation_model: str = "unknown"
    validation_provider_request_id: str | None = None


class RetrievalState(TypedDict, total=False):
    message: str
    request_id: str
    tenant_id: str
    classification: ClassificationResult
    retrieval_query: str
    retrieval: RetrievalResult


class RetrievalExecutor:
    """Cached, filtered and diversity-reranked local Gita retrieval."""

    def __init__(
        self,
        retriever: GitaVectorRetriever,
        validator: RetrievalValidator,
        *,
        tenant_id: str = "default",
        policy: RetrievalPolicy | None = None,
        cache: RetrievalCache | None = None,
        single_flight: SingleFlight | None = None,
        audit_sink: AuditSink | None = None,
        metrics: PhaseOneMetrics | None = None,
    ) -> None:
        self._retriever = retriever
        self._validator = validator
        self._tenant_id = tenant_id
        self._policy = policy or RetrievalPolicy()
        self._cache = cache
        self._single_flight = single_flight or SingleFlight()
        self._audit = audit_sink or NoOpAuditSink()
        self._metrics = metrics or PhaseOneMetrics(NoOpMetricSink())
        self._context = RetrievalCacheKeyContext(
            tenant_id=tenant_id,
            embedding_model=retriever.model_name,
            corpus_sha256=retriever.corpus_sha256,
            pipeline_version=RETRIEVAL_PIPELINE_VERSION,
            reranker_version=RERANKER_VERSION,
            validator_model=validator.model_name,
            validator_prompt_version=validator.prompt_version,
            validator_threshold=validator.threshold,
            candidate_k=self._policy.candidate_k,
            top_k=self._policy.top_k,
            minimum_score=self._policy.minimum_score,
            mmr_lambda=self._policy.mmr_lambda,
            max_per_chapter=self._policy.max_per_chapter,
            allowed_source_ids=self._policy.allowed_source_ids,
            allowed_speakers=self._policy.allowed_speakers,
        )

    @property
    def cache_context(self) -> RetrievalCacheKeyContext:
        return self._context

    def _from_cache(self, query: str, *, request_id: str) -> _Retrieved | None:
        if self._cache is None:
            return None
        started = perf_counter()
        try:
            cached = self._cache.get(query, self._context)
        except Exception as exc:
            self._metrics.cache_lookup(result="error", cache="retrieval")
            logger.warning(
                "phase2.retrieval.cache_error",
                extra={
                    "request_id": request_id,
                    "stage": "retrieval_cache_lookup",
                    "operation": "get",
                    "error_type": type(exc).__name__,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            return None
        if cached is None:
            self._metrics.cache_lookup(result="miss", cache="retrieval")
            logger.info(
                "phase2.retrieval.cache_miss",
                extra={
                    "request_id": request_id,
                    "stage": "retrieval_cache_lookup",
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            return None
        try:
            documents = self._retriever.hydrate(
                {
                    "chunk_id": item.chunk_id,
                    "similarity_score": item.similarity_score,
                    "rerank_score": item.rerank_score,
                    "dense_rank": item.dense_rank,
                    "final_rank": item.final_rank,
                    "validation_probability": item.validation_probability,
                }
                for item in cached.items
            )
        except RetrievalCorpusError:
            try:
                self._cache.delete(query, self._context)
            except Exception:
                pass
            self._metrics.cache_lookup(result="error", cache="retrieval")
            logger.warning(
                "phase2.retrieval.cache_error",
                extra={
                    "request_id": request_id,
                    "stage": "retrieval_cache_lookup",
                    "operation": "hydrate",
                    "error_type": "RetrievalCorpusError",
                },
            )
            return None
        age = max(0.0, time() - cached.stored_at_epoch_seconds)
        self._metrics.cache_lookup(result="hit", cache="retrieval")
        logger.info(
            "phase2.retrieval.cache_hit",
            extra={
                "request_id": request_id,
                "stage": "retrieval_cache_lookup",
                "chunk_count": len(documents),
                "cache_age_seconds": round(age, 3),
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return _Retrieved(
            documents=tuple(documents),
            candidate_count=cached.candidate_count,
            source="cache",
            cache_age_seconds=age,
            validation_rejected_count=cached.validation_rejected_count,
            validation_model=cached.validation_model,
            validation_provider_request_id=cached.validation_provider_request_id,
        )

    def _retrieve_uncached(self, query: str, *, request_id: str) -> _Retrieved:
        policy = self._policy
        started = perf_counter()
        candidates = self._retriever.retrieve(
            query,
            top_k=policy.candidate_k,
            minimum_score=-1.0,
            source_ids=frozenset(policy.allowed_source_ids),
            speakers=frozenset(policy.allowed_speakers),
        )
        logger.info(
            "phase2.retrieval.candidates_retrieved",
            extra={
                "request_id": request_id,
                "stage": "dense_candidate_retrieval",
                "candidate_count": len(candidates),
                "candidate_k": policy.candidate_k,
                "embedding_model": self._retriever.model_name,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )

        filtered = [
            document
            for document in candidates
            if float(document.metadata["similarity_score"]) >= policy.minimum_score
        ]
        logger.info(
            "phase2.retrieval.post_filter_completed",
            extra={
                "request_id": request_id,
                "stage": "retrieval_post_filter",
                "input_count": len(candidates),
                "eligible_count": len(filtered),
                "dropped_count": len(candidates) - len(filtered),
                "minimum_score": policy.minimum_score,
            },
        )

        rerank_started = perf_counter()
        selected = self._retriever.rerank_mmr(
            filtered,
            top_k=policy.top_k,
            mmr_lambda=policy.mmr_lambda,
            max_per_chapter=policy.max_per_chapter,
        )
        logger.info(
            "phase2.retrieval.rerank_completed",
            extra={
                "request_id": request_id,
                "stage": "retrieval_rerank",
                "input_count": len(filtered),
                "output_count": len(selected),
                "top_k": policy.top_k,
                "mmr_lambda": policy.mmr_lambda,
                "max_per_chapter": policy.max_per_chapter,
                "duration_ms": round((perf_counter() - rerank_started) * 1000, 2),
            },
        )

        validation_started = perf_counter()
        validation = self._validator.validate(query, selected)
        validations_by_id = {item.chunk_id: item for item in validation.chunks}
        if len(validations_by_id) != len(selected) or any(
            str(document.metadata["chunk_id"]) not in validations_by_id
            for document in selected
        ):
            raise RetrievalValidationError(
                "JEV validation did not return exactly one decision per passage"
            )
        validated: list[Document] = []
        for document in selected:
            decision = validations_by_id[str(document.metadata["chunk_id"])]
            if not decision.accepted:
                continue
            document.metadata["validation_probability"] = decision.relevance_probability
            document.metadata["final_rank"] = len(validated) + 1
            validated.append(document)
        rejected_count = len(selected) - len(validated)
        self._metrics.retrieval_validation(
            status="passed" if validated else "no_valid_chunks",
            accepted_count=len(validated),
            rejected_count=rejected_count,
        )
        logger.info(
            "phase2.retrieval.jev_validation_completed",
            extra={
                "request_id": request_id,
                "stage": "retrieval_jev_validation",
                "input_count": len(selected),
                "accepted_count": len(validated),
                "rejected_count": rejected_count,
                "validation_threshold": self._validator.threshold,
                "model": validation.model,
                "provider_request_id": validation.provider_request_id,
                "duration_ms": round((perf_counter() - validation_started) * 1000, 2),
            },
        )

        if self._cache is not None and validated:
            items = tuple(
                CachedRetrievalItem(
                    chunk_id=str(document.metadata["chunk_id"]),
                    similarity_score=float(document.metadata["similarity_score"]),
                    rerank_score=float(document.metadata["rerank_score"]),
                    dense_rank=int(document.metadata["dense_rank"]),
                    final_rank=int(document.metadata["final_rank"]),
                    validation_probability=float(
                        document.metadata["validation_probability"]
                    ),
                )
                for document in validated
            )
            try:
                self._cache.put(
                    query,
                    self._context,
                    items,
                    candidate_count=len(candidates),
                    validation_rejected_count=rejected_count,
                    validation_model=validation.model,
                    validation_provider_request_id=validation.provider_request_id,
                )
            except Exception as exc:
                self._metrics.cache_lookup(result="error", cache="retrieval")
                logger.warning(
                    "phase2.retrieval.cache_error",
                    extra={
                        "request_id": request_id,
                        "stage": "retrieval_cache_write",
                        "operation": "set",
                        "error_type": type(exc).__name__,
                    },
                )
            else:
                logger.info(
                    "phase2.retrieval.cache_written",
                    extra={
                        "request_id": request_id,
                        "stage": "retrieval_cache_write",
                        "chunk_count": len(items),
                    },
                )
        return _Retrieved(
            documents=tuple(validated),
            candidate_count=len(candidates),
            source="retriever",
            validation_rejected_count=rejected_count,
            validation_model=validation.model,
            validation_provider_request_id=validation.provider_request_id,
        )

    def execute(self, query: str, *, request_id: str) -> RetrievalResult:
        started = perf_counter()
        safe_query_fields = prompt_log_fields(query, include_content=False)
        logger.info(
            "phase2.retrieval.started",
            extra={
                "request_id": request_id,
                "stage": "retrieval",
                "pipeline_version": RETRIEVAL_PIPELINE_VERSION,
                "candidate_k": self._policy.candidate_k,
                "top_k": self._policy.top_k,
                **safe_query_fields,
            },
        )
        cached = self._from_cache(query, request_id=request_id)
        if cached is None:
            cache_key = (
                self._cache.key_for(query, self._context)
                if self._cache is not None
                else f"uncached:{safe_query_fields['prompt_fingerprint']}"
            )

            def load() -> _Retrieved:
                return self._retrieve_uncached(query, request_id=request_id)

            flight = self._single_flight.do(cache_key, load)
            retrieved = flight.value
            if flight.shared:
                retrieved = _Retrieved(
                    documents=retrieved.documents,
                    candidate_count=retrieved.candidate_count,
                    source="singleflight",
                    cache_age_seconds=retrieved.cache_age_seconds,
                    validation_rejected_count=retrieved.validation_rejected_count,
                    validation_model=retrieved.validation_model,
                    validation_provider_request_id=(
                        retrieved.validation_provider_request_id
                    ),
                )
        else:
            retrieved = cached

        chunks = tuple(self._to_chunk(document) for document in retrieved.documents)
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.info(
            "phase2.retrieval.completed",
            extra={
                "request_id": request_id,
                "stage": "retrieval",
                "source": retrieved.source,
                "candidate_count": retrieved.candidate_count,
                "chunk_count": len(chunks),
                "validation_rejected_count": retrieved.validation_rejected_count,
                "ready_for_generation": bool(chunks),
                "chunk_ids": [chunk.chunk_id for chunk in chunks],
                "citations": [f"{chunk.chapter}.{chunk.verse_label}" for chunk in chunks],
                "duration_ms": duration_ms,
            },
        )
        self._metrics.retrieval_completed(
            source=retrieved.source,
            result_count=len(chunks),
            duration_seconds=duration_ms / 1000,
        )
        self._audit.record(
            AuditEvent(
                event_type="phase2.retrieval.completed",
                request_id=request_id,
                outcome="completed" if chunks else "no_match",
                metadata={
                    "pipeline_version": RETRIEVAL_PIPELINE_VERSION,
                    "source": retrieved.source,
                    "candidate_count": retrieved.candidate_count,
                    "chunk_count": len(chunks),
                    "validation_rejected_count": retrieved.validation_rejected_count,
                    "validation_model": retrieved.validation_model,
                    "validation_provider_request_id": (
                        retrieved.validation_provider_request_id or "unknown"
                    ),
                    "chunk_ids": [chunk.chunk_id for chunk in chunks],
                },
            )
        )
        return RetrievalResult(
            source=cast(Any, retrieved.source),
            cache_age_seconds=retrieved.cache_age_seconds,
            candidate_count=retrieved.candidate_count,
            validation_rejected_count=retrieved.validation_rejected_count,
            validation_model=retrieved.validation_model,
            validation_threshold=self._validator.threshold,
            validation_provider_request_id=retrieved.validation_provider_request_id,
            ready_for_generation=bool(chunks),
            chunks=chunks,
        )

    @staticmethod
    def _to_chunk(document: Document) -> RetrievedChunk:
        metadata = document.metadata
        return RetrievedChunk(
            chunk_id=str(metadata["chunk_id"]),
            source_id=str(metadata["source_id"]),
            chapter=int(metadata["chapter"]),
            chapter_title=str(metadata["chapter_title"]),
            verse_start=int(metadata["verse_start"]),
            verse_end=int(metadata["verse_end"]),
            verse_label=str(metadata["verse_label"]),
            speaker=str(metadata["speaker"]),
            source_pdf_page=int(metadata["source_pdf_page"]),
            translation=document.page_content,
            similarity_score=float(metadata["similarity_score"]),
            rerank_score=float(metadata["rerank_score"]),
            dense_rank=int(metadata["dense_rank"]),
            final_rank=int(metadata["final_rank"]),
            validation_probability=float(metadata["validation_probability"]),
        )


def build_filtered_retrieval_chain(
    executor: RetrievalExecutor,
) -> Runnable[RetrievalState, RetrievalState]:
    """Build named LangChain spans for eligibility/query preparation and retrieval."""

    def pre_filter(state: RetrievalState) -> RetrievalState:
        classification = ClassificationResult.model_validate(state["classification"])
        if not classification.in_scope:
            raise RetrievalNotEligible("Out-of-scope classifications are not retrieved")
        if classification.needs_review or classification.low_confidence_fields:
            raise RetrievalNotEligible("Low-confidence classifications require review")
        query = build_classification_query(state["message"], classification)
        logger.info(
            "phase2.retrieval.pre_filter_completed",
            extra={
                "request_id": state["request_id"],
                "stage": "retrieval_pre_filter",
                "in_scope": classification.in_scope,
                "needs_review": classification.needs_review,
                "allowed_source_count": len(executor.cache_context.allowed_source_ids),
                "allowed_speaker_count": len(executor.cache_context.allowed_speakers),
            },
        )
        return {**state, "classification": classification, "retrieval_query": query}

    def retrieve(state: RetrievalState) -> RetrievalState:
        result = executor.execute(
            state["retrieval_query"], request_id=state["request_id"]
        )
        return {**state, "retrieval": result}

    prepare = RunnableLambda(pre_filter).with_config(
        run_name="pre_filter_gita_retrieval",
        tags=["phase-2", "retrieval", "filter"],
    )
    execute = RunnableLambda(retrieve).with_config(
        run_name="retrieve_rerank_cache_gita_chunks",
        tags=["phase-2", "retrieval", "rerank", "cache"],
    )
    return cast(
        Runnable[RetrievalState, RetrievalState],
        (prepare | execute).with_config(
            run_name="filtered_gita_retrieval",
            tags=["phase-2", "retrieval"],
        ),
    )


def invoke_retrieval_chain(
    chain: Runnable[RetrievalState, RetrievalState],
    *,
    message: str,
    classification: ClassificationResult,
    request_id: str,
    tenant_id: str = "default",
) -> RetrievalResult:
    config: RunnableConfig = {
        "run_name": "phase_two_retrieval_request",
        "tags": ["phase-2", "retrieval"],
        "metadata": {
            "request_id": request_id,
            "pipeline_version": RETRIEVAL_PIPELINE_VERSION,
        },
    }
    with request_logging_context(request_id):
        output = chain.invoke(
            {
                "message": message,
                "classification": classification,
                "request_id": request_id,
                "tenant_id": tenant_id,
            },
            config=config,
        )
    return output["retrieval"]
