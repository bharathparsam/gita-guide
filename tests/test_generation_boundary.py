from __future__ import annotations

import pytest

from app.models.classification import ClassificationResult
from app.models.retrieval import GroundingContext, RetrievedChunk, RetrievalResult
from app.services.generation_service import (
    GenerationNotReadyError,
    build_grounded_generation_input,
)


def _classification() -> ClassificationResult:
    return ClassificationResult(
        in_scope=True,
        in_scope_probability=0.95,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.9,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="attachment_to_results",
        root_conflict_confidence=0.9,
    )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="gita:2:47",
        source_id="gita-test",
        chapter=2,
        chapter_title="Knowledge",
        verse_start=47,
        verse_end=47,
        verse_label="47",
        speaker="The Blessed Lord said",
        source_pdf_page=10,
        translation="Act without attachment to results.",
        similarity_score=0.8,
        rerank_score=0.6,
        dense_rank=1,
        final_rank=1,
        validation_probability=0.91,
    )


def test_generation_input_accepts_only_jev_validated_grounding() -> None:
    context = GroundingContext(
        request_id="request-1",
        classification=_classification(),
        retrieval=RetrievalResult(
            source="retriever",
            candidate_count=20,
            validation_rejected_count=4,
            validation_model="test-jev",
            validation_threshold=0.65,
            validation_provider_request_id="validation-1",
            ready_for_generation=True,
            chunks=(_chunk(),),
        ),
    )

    generation_input = build_grounded_generation_input("I fear the result", context)

    assert generation_input.passages == (_chunk(),)
    assert generation_input.validation_threshold == 0.65


def test_generation_input_fails_closed_without_validated_passages() -> None:
    context = GroundingContext(
        request_id="request-2",
        classification=_classification(),
        retrieval=RetrievalResult(
            source="retriever",
            candidate_count=20,
            validation_rejected_count=5,
            validation_model="test-jev",
            validation_threshold=0.65,
            ready_for_generation=False,
            chunks=(),
        ),
    )

    with pytest.raises(GenerationNotReadyError, match="No JEV-approved"):
        build_grounded_generation_input("I fear the result", context)
