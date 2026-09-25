from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pytest

from app.cache import HmacCacheKeyBuilder, InMemoryCacheBackend, RetrievalCache
from app.models.classification import ClassificationResult
from app.observability.audit import InMemoryAuditSink
from app.observability.metrics import InMemoryMetricSink, PhaseOneMetrics
from app.retrieval.gita_vector_retriever import GitaVectorRetriever
from app.retrieval.jev_relevance_validator import (
    ChunkValidation,
    RetrievalValidation,
)
from app.services.retrieval_service import (
    RetrievalExecutor,
    RetrievalNotEligible,
    RetrievalPolicy,
    build_filtered_retrieval_chain,
    invoke_retrieval_chain,
)


class CountingEmbeddings:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [1.0, 0.0]


class FailingCacheBackend:
    def get(self, key: str) -> bytes | None:
        raise ConnectionError("cache unavailable")

    def set(self, key: str, value: bytes, *, ttl_seconds: int) -> None:
        raise ConnectionError("cache unavailable")

    def delete(self, key: str) -> bool:
        raise ConnectionError("cache unavailable")


class AcceptingValidator:
    model_name = "test-jev-validator"
    prompt_version = "test-validator-v1"
    threshold = 0.65

    def __init__(self) -> None:
        self.calls = 0

    def validate(self, retrieval_query, documents) -> RetrievalValidation:
        self.calls += 1
        return RetrievalValidation(
            chunks=tuple(
                ChunkValidation(
                    chunk_id=str(document.metadata["chunk_id"]),
                    relevance_probability=0.9,
                    accepted=True,
                )
                for document in documents
            ),
            model=self.model_name,
            provider_request_id="validation-123",
        )


class RejectingValidator(AcceptingValidator):
    def validate(self, retrieval_query, documents) -> RetrievalValidation:
        self.calls += 1
        return RetrievalValidation(
            chunks=tuple(
                ChunkValidation(
                    chunk_id=str(document.metadata["chunk_id"]),
                    relevance_probability=0.2,
                    accepted=False,
                )
                for document in documents
            ),
            model=self.model_name,
            provider_request_id="validation-rejected",
        )


class AlternatingValidator(AcceptingValidator):
    def validate(self, retrieval_query, documents) -> RetrievalValidation:
        self.calls += 1
        return RetrievalValidation(
            chunks=tuple(
                ChunkValidation(
                    chunk_id=str(document.metadata["chunk_id"]),
                    relevance_probability=0.9 if index % 2 == 0 else 0.2,
                    accepted=index % 2 == 0,
                )
                for index, document in enumerate(documents)
            ),
            model=self.model_name,
            provider_request_id="validation-partial",
        )

def _classification(*, needs_review: bool = False) -> ClassificationResult:
    return ClassificationResult(
        in_scope=True,
        in_scope_probability=0.95,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.9,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="attachment_to_results",
        root_conflict_confidence=0.9,
        needs_review=needs_review,
        low_confidence_fields=("primary_emotion",) if needs_review else (),
    )


def _retriever(embeddings: CountingEmbeddings) -> GitaVectorRetriever:
    chunks = []
    vectors = []
    for index in range(9):
        chapter = 2 + index // 2
        chunks.append(
            {
                "chunk_id": f"gita-test:{chapter}:{index + 1}",
                "source_id": "gita-test",
                "chapter": chapter,
                "chapter_title": f"Chapter {chapter}",
                "verse_start": index + 1,
                "verse_end": index + 1,
                "verse_label": str(index + 1),
                "speaker": "Krishna" if index < 8 else "Arjuna",
                "source_pdf_page": 10 + index,
                "translation": f"Guidance passage {index + 1}",
            }
        )
        # The last Krishna passage is below the configured relevance floor.
        vectors.append([1.0 - index * 0.08, index * 0.04] if index < 7 else [-1.0, 0.0])
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    return GitaVectorRetriever(
        chunks=chunks,
        vectors=matrix,
        embeddings=embeddings,
        model_name="test-embedding",
        corpus_sha256="a" * 64,
        query_prefix="",
    )


def test_filtered_retrieval_returns_at_most_five_and_cache_avoids_embedding() -> None:
    embeddings = CountingEmbeddings()
    retriever = _retriever(embeddings)
    backend = InMemoryCacheBackend()
    cache = RetrievalCache(
        backend,
        HmacCacheKeyBuilder("x" * 32),
        ttl_seconds=300,
    )
    audit = InMemoryAuditSink()
    validator = AcceptingValidator()
    executor = RetrievalExecutor(
        retriever,
        validator,
        tenant_id="tenant-a",
        policy=RetrievalPolicy(
            candidate_k=8,
            top_k=5,
            minimum_score=0.0,
            mmr_lambda=0.8,
            max_per_chapter=2,
            allowed_source_ids=("gita-test",),
            allowed_speakers=("Krishna",),
        ),
        cache=cache,
        audit_sink=audit,
        metrics=PhaseOneMetrics(InMemoryMetricSink()),
    )
    chain = build_filtered_retrieval_chain(executor)

    first = invoke_retrieval_chain(
        chain,
        message="I am anxious about the result",
        classification=_classification(),
        request_id="request-1",
        tenant_id="tenant-a",
    )
    second = invoke_retrieval_chain(
        chain,
        message="I am anxious about the result",
        classification=_classification(),
        request_id="request-2",
        tenant_id="tenant-a",
    )

    assert first.source == "retriever"
    assert second.source == "cache"
    assert len(first.chunks) == 5
    assert [chunk.final_rank for chunk in first.chunks] == [1, 2, 3, 4, 5]
    assert all(chunk.speaker == "Krishna" for chunk in first.chunks)
    assert all(chunk.similarity_score >= 0 for chunk in first.chunks)
    assert max(Counter(chunk.chapter for chunk in first.chunks).values()) <= 2
    assert embeddings.queries == [
        "User situation: I am anxious about the result\n"
        "Primary situation: outcome anxiety\n"
        "Primary emotion: fear\n"
        "Root conflict: attachment to results"
    ]
    assert validator.calls == 1
    assert first.ready_for_generation is True
    assert all(chunk.validation_probability == 0.9 for chunk in first.chunks)
    assert [chunk.chunk_id for chunk in second.chunks] == [
        chunk.chunk_id for chunk in first.chunks
    ]
    assert [event.event_type for event in audit.events] == [
        "phase2.retrieval.completed",
        "phase2.retrieval.completed",
    ]

    key = cache.key_for(embeddings.queries[0], executor.cache_context)
    stored = backend.get(key)
    assert stored is not None
    assert b"anxious" not in stored
    assert b"Guidance passage" not in stored
    payload = json.loads(stored)
    assert len(payload["items"]) == 5


def test_retrieval_pre_filter_rejects_low_confidence_classification() -> None:
    embeddings = CountingEmbeddings()
    executor = RetrievalExecutor(
        _retriever(embeddings),
        AcceptingValidator(),
        policy=RetrievalPolicy(
            allowed_source_ids=("gita-test",),
            allowed_speakers=("Krishna",),
        ),
    )

    with pytest.raises(RetrievalNotEligible, match="require review"):
        invoke_retrieval_chain(
            build_filtered_retrieval_chain(executor),
            message="I do not know what to do",
            classification=_classification(needs_review=True),
            request_id="request-review",
        )

    assert embeddings.queries == []


def test_retrieval_cache_outage_fails_open_to_local_retrieval() -> None:
    embeddings = CountingEmbeddings()
    cache = RetrievalCache(
        FailingCacheBackend(),  # type: ignore[arg-type]
        HmacCacheKeyBuilder("x" * 32),
    )
    executor = RetrievalExecutor(
        _retriever(embeddings),
        AcceptingValidator(),
        policy=RetrievalPolicy(
            allowed_source_ids=("gita-test",),
            allowed_speakers=("Krishna",),
        ),
        cache=cache,
    )

    result = invoke_retrieval_chain(
        build_filtered_retrieval_chain(executor),
        message="I am anxious about the result",
        classification=_classification(),
        request_id="request-cache-down",
    )

    assert result.source == "retriever"
    assert len(result.chunks) == 5
    assert len(embeddings.queries) == 1


def test_retrieval_does_not_mark_context_ready_when_jev_rejects_all_chunks() -> None:
    embeddings = CountingEmbeddings()
    validator = RejectingValidator()
    executor = RetrievalExecutor(
        _retriever(embeddings),
        validator,
        policy=RetrievalPolicy(
            allowed_source_ids=("gita-test",),
            allowed_speakers=("Krishna",),
        ),
    )

    result = invoke_retrieval_chain(
        build_filtered_retrieval_chain(executor),
        message="I am anxious about the result",
        classification=_classification(),
        request_id="request-no-grounding",
    )

    assert result.chunks == ()
    assert result.validation_rejected_count == 5
    assert result.ready_for_generation is False


def test_only_jev_approved_chunks_are_cached_and_final_ranks_are_compacted() -> None:
    embeddings = CountingEmbeddings()
    validator = AlternatingValidator()
    backend = InMemoryCacheBackend()
    cache = RetrievalCache(backend, HmacCacheKeyBuilder("x" * 32))
    executor = RetrievalExecutor(
        _retriever(embeddings),
        validator,
        policy=RetrievalPolicy(
            allowed_source_ids=("gita-test",),
            allowed_speakers=("Krishna",),
        ),
        cache=cache,
    )
    chain = build_filtered_retrieval_chain(executor)

    first = invoke_retrieval_chain(
        chain,
        message="I am anxious about the result",
        classification=_classification(),
        request_id="request-partial-1",
    )
    second = invoke_retrieval_chain(
        chain,
        message="I am anxious about the result",
        classification=_classification(),
        request_id="request-partial-2",
    )

    assert len(first.chunks) == 3
    assert first.validation_rejected_count == 2
    assert [chunk.final_rank for chunk in first.chunks] == [1, 2, 3]
    assert all(chunk.validation_probability == 0.9 for chunk in first.chunks)
    assert second.source == "cache"
    assert [chunk.chunk_id for chunk in second.chunks] == [
        chunk.chunk_id for chunk in first.chunks
    ]
    assert validator.calls == 1
