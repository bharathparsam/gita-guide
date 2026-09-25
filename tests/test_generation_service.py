from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from app.guardrails.input_safety import (
    GuardrailDecision,
    InputSafetyAction,
)
from app.models.classification import ClassificationResult
from app.models.generation import GroundedGenerationInput
from app.models.retrieval import RetrievedChunk
from app.observability.audit import InMemoryAuditSink
from app.services.generation_service import (
    GenerationError,
    GroundedGuidanceGenerator,
    OutputSafetyError,
)


class FakeChatModel:
    def __init__(
        self,
        content: str,
        *,
        response_metadata: dict[str, str] | None = None,
    ) -> None:
        self.content = content
        self.response_metadata = response_metadata or {"model_name": "test-nemotron"}
        self.inputs = []

    def invoke(self, input, config=None):
        self.inputs.append((input, config))
        return AIMessage(
            content=self.content,
            id="provider-generation-1",
            response_metadata=self.response_metadata,
        )


def _input() -> GroundedGenerationInput:
    classification = ClassificationResult(
        in_scope=True,
        in_scope_probability=0.95,
        primary_situation="outcome_anxiety",
        primary_situation_confidence=0.9,
        primary_emotion="fear",
        primary_emotion_confidence=0.9,
        root_conflict="attachment_to_results",
        root_conflict_confidence=0.9,
    )
    passage = RetrievedChunk(
        chunk_id="gita:2:47",
        source_id="gita-test",
        chapter=2,
        chapter_title="Knowledge",
        verse_start=47,
        verse_end=47,
        verse_label="47",
        speaker="The Blessed Lord said",
        source_pdf_page=10,
        translation="Your right is to work only, never to its fruits.",
        similarity_score=0.8,
        rerank_score=0.7,
        dense_rank=1,
        final_rank=1,
        validation_probability=0.91,
    )
    return GroundedGenerationInput(
        request_id="request-generation",
        message="I am anxious about my interview result",
        classification=classification,
        passages=(passage,),
        validation_model="test-jev",
        validation_threshold=0.65,
    )


def _allow(_: str) -> GuardrailDecision:
    return GuardrailDecision(action=InputSafetyAction.ALLOW, provider="test-output-rail")


def test_grounded_generator_accepts_only_supported_citations() -> None:
    model = FakeChatModel(
        "Focus on your effort while releasing control of the result "
        "[Bhagavad Gita 2.47]."
    )
    audit = InMemoryAuditSink()
    generator = GroundedGuidanceGenerator(
        model,
        model_name="test-nemotron",
        output_guardrail=_allow,
        audit_sink=audit,
    )

    response = generator.generate(_input())

    assert response.citations == ("Bhagavad Gita 2.47",)
    assert response.grounded_chunk_ids == ("gita:2:47",)
    assert response.provider_request_id is None
    assert response.langchain_run_id == "provider-generation-1"
    assert "Your right is to work only" in model.inputs[0][0].to_string()
    assert audit.events[-1].event_type == "phase3.generation.completed"


def test_grounded_generator_rejects_hallucinated_citation() -> None:
    generator = GroundedGuidanceGenerator(
        FakeChatModel("Trust the path [Bhagavad Gita 18.66]."),
        model_name="test-nemotron",
        output_guardrail=_allow,
    )

    with pytest.raises(GenerationError, match="unsupported passages"):
        generator.generate(_input())


def test_grounded_generator_fails_closed_on_output_safety_block() -> None:
    def block(_: str) -> GuardrailDecision:
        return GuardrailDecision(
            action=InputSafetyAction.BLOCK,
            provider="test-output-rail",
        )

    generator = GroundedGuidanceGenerator(
        FakeChatModel("Grounded guidance [Bhagavad Gita 2.47]."),
        model_name="test-nemotron",
        output_guardrail=block,
    )

    with pytest.raises(OutputSafetyError):
        generator.generate(_input())


def test_grounded_generator_rejects_truncated_completion() -> None:
    generator = GroundedGuidanceGenerator(
        FakeChatModel(
            "Partial guidance [Bhagavad Gita 2.47].",
            response_metadata={
                "model_name": "test-nemotron",
                "finish_reason": "length",
            },
        ),
        model_name="test-nemotron",
        output_guardrail=_allow,
    )

    with pytest.raises(GenerationError, match="truncated"):
        generator.generate(_input())


def test_grounded_generator_rejects_reasoning_leakage() -> None:
    generator = GroundedGuidanceGenerator(
        FakeChatModel(
            "Here's a thinking process: analyze the user first. "
            "[Bhagavad Gita 2.47]."
        ),
        model_name="test-nemotron",
        output_guardrail=_allow,
    )

    with pytest.raises(GenerationError, match="internal reasoning"):
        generator.generate(_input())
