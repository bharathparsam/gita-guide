from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class ClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    in_scope: bool
    in_scope_probability: float = Field(ge=0, le=1)
    primary_situation: Situation
    primary_situation_confidence: float = Field(ge=0, le=1)
    primary_emotion: Emotion
    primary_emotion_confidence: float = Field(ge=0, le=1)
    root_conflict: RootConflict
    root_conflict_confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
    low_confidence_fields: tuple[str, ...] = ()
    provider_request_id: str | None = None
    model: str | None = None
