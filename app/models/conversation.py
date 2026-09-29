from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_CONVERSATION_SUMMARY_CHARS = 2_000
MAX_CONVERSATION_TURN_CHARS = 2_000
MAX_RECENT_CONVERSATION_TURNS = 8

_UNSAFE_FORMAT_CHARACTERS = re.compile(
    "[\u061c\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]"
)
_UNSAFE_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_conversation_text(value: str) -> str:
    """Normalize untrusted conversation data before it reaches a prompt.

    Prompt injection cannot be solved by string filtering. This function only
    removes invisible/control characters that can obscure prompt boundaries;
    the prompts must still treat all conversation content as quoted data.
    """

    normalized = unicodedata.normalize("NFKC", value)
    normalized = _UNSAFE_FORMAT_CHARACTERS.sub("", normalized)
    normalized = _UNSAFE_CONTROL_CHARACTERS.sub("", normalized)
    return normalized.strip()


class ConversationTurn(BaseModel):
    """One bounded, untrusted historical message supplied by a client."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_CONVERSATION_TURN_CHARS)

    @field_validator("content", mode="before")
    @classmethod
    def normalize_content(cls, value: object) -> object:
        if isinstance(value, str):
            return sanitize_conversation_text(value)
        return value


class ConversationContext(BaseModel):
    """Portable rolling memory; persistence belongs to the calling layer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0"] = "1.0"
    summary: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_CONVERSATION_SUMMARY_CHARS,
    )
    recent_turns: tuple[ConversationTurn, ...] = Field(
        default=(),
        max_length=MAX_RECENT_CONVERSATION_TURNS,
    )

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = sanitize_conversation_text(value)
            return cleaned or None
        return value

    @model_validator(mode="after")
    def validate_complete_exchanges(self) -> ConversationContext:
        if not self.recent_turns:
            return self
        if len(self.recent_turns) % 2 != 0:
            raise ValueError("recent_turns must contain complete user/assistant exchanges")
        for index, turn in enumerate(self.recent_turns):
            expected = "user" if index % 2 == 0 else "assistant"
            if turn.role != expected:
                raise ValueError(
                    "recent_turns must alternate user and assistant, starting with user"
                )
        return self


class ConversationMemoryUpdate(BaseModel):
    """Result of applying the rolling-summary policy to conversation memory."""

    model_config = ConfigDict(extra="forbid")

    context: ConversationContext
    summary_updated: bool
    summary_deferred: bool = False
    summarized_turn_count: int = Field(default=0, ge=0)

