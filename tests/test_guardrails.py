import logging
from unittest.mock import Mock

import pytest

from app.config import Settings
from app.guardrails.input_safety import (
    GuardrailUnavailableError,
    InputSafetyAction,
    NvidiaSafetyGuardrail,
)


def settings(*, url: str | None = "http://localhost:8001/v1", required: bool = False) -> Settings:
    return Settings(
        openrouter_api_key="test-key",
        openrouter_model="typesafe/jev-1.13",
        openrouter_timeout_seconds=3,
        classification_scope_threshold=0.5,
        classification_min_confidence=0.6,
        nvidia_guardrail_url=url,
        nvidia_guardrail_model="nvidia/test-safety-model",
        nvidia_guardrail_api_key="EMPTY",
        nvidia_guardrail_required=required,
    )


def model_response(verdict: str) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"content": f"Prompt harm: {verdict}"}}]
    }
    return response


def test_nvidia_guardrail_allows_safe_verdict() -> None:
    session = Mock()
    session.post.return_value = model_response("unharmful")

    decision = NvidiaSafetyGuardrail(settings(), session=session).check(
        "I am grieving and need perspective"
    )

    assert decision.action is InputSafetyAction.ALLOW
    assert session.post.call_args.args[0].endswith("/chat/completions")
    assert session.post.call_args.kwargs["json"]["chat_template_kwargs"] == {
        "request_categories": "/categories"
    }


def test_nvidia_model_prompt_emits_an_audit_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOG_PROMPT_CONTENT", raising=False)
    session = Mock()
    session.post.return_value = model_response("unharmful")
    records: list[logging.LogRecord] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    guardrail_logger = logging.getLogger("gita_guide.guardrails")
    previous_level = guardrail_logger.level
    handler = CaptureHandler()
    guardrail_logger.setLevel(logging.INFO)
    guardrail_logger.addHandler(handler)
    try:
        NvidiaSafetyGuardrail(settings(), session=session).check("I feel worried")
    finally:
        guardrail_logger.removeHandler(handler)
        guardrail_logger.setLevel(previous_level)

    prompt_record = next(
        record for record in records if record.getMessage() == "model.prompt.prepared"
    )
    assert prompt_record.prompt_kind == "content_safety"  # type: ignore[attr-defined]
    assert len(prompt_record.prompt_fingerprint) == 64  # type: ignore[attr-defined]
    assert not hasattr(prompt_record, "prompt")


def test_nvidia_guardrail_blocks_harmful_verdict() -> None:
    session = Mock()
    session.post.return_value = model_response("harmful")

    decision = NvidiaSafetyGuardrail(settings(), session=session).check("unsafe input")

    assert decision.action is InputSafetyAction.BLOCK
    assert "nvidia_content_safety" in decision.categories


def test_nvidia_guardrail_parses_native_unsafe_categories() -> None:
    session = Mock()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "User Safety: unsafe\nSafety Categories: Profanity, Harassment"
                }
            }
        ]
    }
    session.post.return_value = response

    decision = NvidiaSafetyGuardrail(settings(), session=session).check("unsafe input")

    assert decision.action is InputSafetyAction.BLOCK
    assert decision.categories == ("Profanity", "Harassment")


def test_nvidia_guardrail_escalates_native_self_harm_category() -> None:
    session = Mock()
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "User Safety: unsafe\nSafety Categories: Suicide and Self Harm"
                }
            }
        ]
    }
    session.post.return_value = response

    decision = NvidiaSafetyGuardrail(settings(), session=session).check("concerning input")

    assert decision.action is InputSafetyAction.ESCALATE


def test_required_nvidia_guardrail_fails_closed_without_url() -> None:
    with pytest.raises(GuardrailUnavailableError):
        NvidiaSafetyGuardrail(settings(url=None, required=True)).check("hello")
