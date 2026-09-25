from __future__ import annotations

from unittest.mock import Mock

import pytest
from langchain_core.documents import Document

from app.config import Settings
from app.retrieval.jev_relevance_validator import (
    JevRetrievalValidator,
    RetrievalValidationError,
)


def _settings() -> Settings:
    return Settings(
        openrouter_api_key="test-key",
        openrouter_model="typesafe/jev-1.13",
        openrouter_timeout_seconds=3,
        classification_scope_threshold=0.5,
        classification_min_confidence=0.6,
        nvidia_guardrail_url=None,
        nvidia_guardrail_model="test-safety-model",
        nvidia_guardrail_api_key="EMPTY",
        nvidia_guardrail_required=False,
    )


def _documents() -> list[Document]:
    return [
        Document(
            page_content="Act without attachment to results.",
            metadata={"chunk_id": "gita:2:47", "chapter": 2, "verse_label": "47"},
        ),
        Document(
            page_content="A passage unrelated to this situation.",
            metadata={"chunk_id": "gita:10:1", "chapter": 10, "verse_label": "1"},
        ),
    ]


def _response() -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "id": "validation-decision-1",
        "model": "typesafe/jev-1.13-snapshot",
        "answers": {
            "candidate_0_relevant": {"type": "noul", "noul": 0.92},
            "candidate_0_groundable": {"type": "noul", "noul": 0.88},
            "candidate_1_relevant": {"type": "noul", "noul": 0.22},
            "candidate_1_groundable": {"type": "noul", "noul": 0.81},
        },
    }
    return response


def test_jev_validates_all_retrieved_chunks_in_one_typed_request() -> None:
    session = Mock()
    session.post.return_value = _response()
    validator = JevRetrievalValidator(
        _settings(),
        threshold=0.65,
        session=session,
    )

    result = validator.validate(
        "User situation: anxious about results\nRoot conflict: attachment to results",
        _documents(),
    )

    assert session.post.call_count == 1
    assert [item.accepted for item in result.chunks] == [True, False]
    assert [item.relevance_probability for item in result.chunks] == [0.88, 0.22]
    assert result.provider_request_id == "validation-decision-1"
    payload = session.post.call_args.kwargs["json"]
    assert set(payload["questions"]) == {
        "candidate_0_relevant",
        "candidate_0_groundable",
        "candidate_1_relevant",
        "candidate_1_groundable",
    }
    assert payload["state"]["candidate_0"]["candidate_id"] == "gita:2:47"


def test_jev_retrieval_validation_fails_closed_on_missing_decision() -> None:
    session = Mock()
    response = _response()
    del response.json.return_value["answers"]["candidate_1_relevant"]
    session.post.return_value = response
    validator = JevRetrievalValidator(_settings(), session=session)

    with pytest.raises(RetrievalValidationError, match="candidate_1_relevant"):
        validator.validate("context", _documents())
