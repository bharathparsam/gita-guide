from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.classifiers.taxonomy import GITA_TRAITS


Situation = Literal[
    "fear_of_failure",
    "outcome_anxiety",
    "comparison",
    "anger",
    "grief",
    "confusion",
    "lack_of_motivation",
    "purpose",
    "discipline",
    "relationship_conflict",
    "other",
]

Emotion = Literal[
    "fear",
    "sadness",
    "anger",
    "envy",
    "guilt",
    "confusion",
    "frustration",
    "hopelessness",
    "calm",
    "other",
]

RootConflict = Literal[
    "attachment_to_results",
    "fear",
    "comparison",
    "ego",
    "desire",
    "duty_conflict",
    "lack_of_self_control",
    "loss",
    "uncertainty",
    "other",
]

GitaTrait = Literal[*tuple(GITA_TRAITS)]


class ClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1"] = "1.1"
    in_scope: bool
    in_scope_probability: float = Field(ge=0, le=1)
    primary_situation: Situation
    primary_situation_confidence: float = Field(ge=0, le=1)
    primary_emotion: Emotion
    primary_emotion_confidence: float = Field(ge=0, le=1)
    root_conflict: RootConflict
    root_conflict_confidence: float = Field(ge=0, le=1)
    primary_trait: GitaTrait | None = None
    primary_trait_confidence: float | None = Field(default=None, ge=0, le=1)
    needs_review: bool = False
    low_confidence_fields: tuple[str, ...] = ()
    provider_request_id: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def validate_trait_pair(self) -> ClassificationResult:
        if (self.primary_trait is None) != (self.primary_trait_confidence is None):
            raise ValueError(
                "primary_trait and primary_trait_confidence must be provided together"
            )
        return self
