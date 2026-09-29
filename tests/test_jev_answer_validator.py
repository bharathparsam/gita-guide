from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests

from app.config import Settings
from app.guardrails.grounding import AnswerValidationError, JevAnswerValidator
from app.models.retrieval import RetrievedChunk


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="test",
        openrouter_model="typesafe/jev-1.13",
        openrouter_timeout_seconds=3,
        classification_scope_threshold=0.5,
        classification_min_confidence=0.6,
        nvidia_guardrail_url=None,
        nvidia_guardrail_model="test",
        nvidia_guardrail_api_key="EMPTY",
        nvidia_guardrail_required=False,
    )


def _passage() -> RetrievedChunk:
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
        translation="Your right is to work only, never to its fruits.",
        similarity_score=0.8,
        rerank_score=0.7,
        dense_rank=1,
        final_rank=1,
        validation_probability=0.9,
    )


def _response(probabilities: dict[str, float]) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "id": "answer-decision-1",
        "model": "typesafe/jev-test",
        "answers": {
            key: {"type": "noul", "noul": value}
            for key, value in probabilities.items()
        },
    }
    return response


def test_answer_validator_accepts_only_when_every_dimension_passes() -> None:
    session = Mock()
    session.post.return_value = _response(
        {
            "faithful": 0.93,
            "citation_coverage": 0.91,
            "helpful": 0.84,
            "preserves_agency": 0.99,
        }
    )
    result = JevAnswerValidator(_settings(), session=session).validate(
        user_message="I fear the result",
        guidance="Focus on effort [Bhagavad Gita 2.47].",
        passages=(_passage(),),
    )

    assert result.accepted is True
    assert result.helpfulness_probability == 0.84
    payload = session.post.call_args.kwargs["json"]
    assert set(payload["questions"]) == {
        "faithful",
        "citation_coverage",
        "helpful",
        "preserves_agency",
    }
    assert "immediately feasible" in payload["questions"]["helpful"]["instructions"]
    assert "specialized contemplative techniques" in payload["questions"]["helpful"]["instructions"]
    agency_prompt = payload["questions"]["preserves_agency"]["instructions"]
    assert "assistant-authored framing" in agency_prompt
    assert "clearly attributed exact quotation" in agency_prompt
    assert "instruction to the user" in agency_prompt
    assert result.failed_dimensions == ()


def test_answer_validator_uses_weakest_dimension_and_fails_closed() -> None:
    session = Mock()
    session.post.return_value = _response(
        {
            "faithful": 0.7,
            "citation_coverage": 0.95,
            "helpful": 0.9,
            "preserves_agency": 0.99,
        }
    )
    result = JevAnswerValidator(_settings(), session=session).validate(
        user_message="I fear the result",
        guidance="Advice [Bhagavad Gita 2.47].",
        passages=(_passage(),),
    )
    assert result.accepted is False
    assert result.failed_dimensions == ("faithfulness",)

    session.post.return_value = _response(
        {
            "faithful": 1.2,
            "citation_coverage": 0.95,
            "helpful": 0.9,
            "preserves_agency": 0.99,
        }
    )
    with pytest.raises(AnswerValidationError):
        JevAnswerValidator(_settings(), session=session).validate(
            user_message="I fear the result",
            guidance="Advice [Bhagavad Gita 2.47].",
            passages=(_passage(),),
        )


def test_answer_validator_supports_stricter_agency_gate() -> None:
    session = Mock()
    session.post.return_value = _response(
        {
            "faithful": 0.93,
            "citation_coverage": 0.91,
            "helpful": 0.84,
            "preserves_agency": 0.89,
        }
    )

    result = JevAnswerValidator(
        _settings(),
        threshold=0.75,
        agency_threshold=0.90,
        session=session,
    ).validate(
        user_message="I fear the result",
        guidance="Advice [Bhagavad Gita 2.47].",
        passages=(_passage(),),
    )

    assert result.accepted is False
    assert result.failed_dimensions == ("agency",)


def test_answer_validator_fails_closed_on_provider_timeout() -> None:
    session = Mock()
    session.post.side_effect = requests.Timeout("provider timeout")
    with pytest.raises(AnswerValidationError, match="validation failed"):
        JevAnswerValidator(_settings(), session=session).validate(
            user_message="I fear the result",
            guidance="Advice [Bhagavad Gita 2.47].",
            passages=(_passage(),),
        )
    assert session.post.call_count == 2
