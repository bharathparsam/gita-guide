from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.classification import ClassificationResult, GitaTrait
from app.models.conversation import ConversationContext
from app.models.retrieval import RetrievedChunk


class GroundedGenerationInput(BaseModel):
    """The only input contract accepted by the future guidance generator."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: str
    message: str = Field(min_length=1, max_length=4_000)
    conversation_context: ConversationContext = Field(
        default_factory=ConversationContext
    )
    classification: ClassificationResult
    passages: tuple[RetrievedChunk, ...] = Field(min_length=1, max_length=5)
    validation_model: str
    validation_threshold: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_passage_approval(self) -> GroundedGenerationInput:
        if any(
            passage.validation_probability < self.validation_threshold
            for passage in self.passages
        ):
            raise ValueError("generation input contains a passage rejected by JEV")
        return self


class GuidancePresentation(BaseModel):
    """Stable UI contract for the online reflection card."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    trait_id: GitaTrait
    label: str = Field(min_length=1, max_length=80)
    what_krishna_said: str = Field(min_length=1, max_length=1_500)
    how_to_overcome: str = Field(min_length=1, max_length=1_500)
    verse: str = Field(pattern=r"^\d{1,2}\.\d{1,3}(?:-\d{1,3})?$")
    sloka: str = Field(min_length=1, max_length=1_500)


class GuidanceResponse(BaseModel):
    """Citation-checked, output-filtered guidance returned by the generator."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    request_id: str
    guidance: str = Field(min_length=1)
    presentation: GuidancePresentation
    citations: tuple[str, ...] = Field(min_length=1, max_length=5)
    grounded_chunk_ids: tuple[str, ...] = Field(min_length=1, max_length=5)
    model: str
    provider_request_id: str | None = None
    langchain_run_id: str | None = None
    validation_model: str
    validation_provider_request_id: str | None = None
    faithfulness_probability: float = Field(ge=0, le=1)
    citation_coverage_probability: float = Field(ge=0, le=1)
    helpfulness_probability: float = Field(ge=0, le=1)
    agency_probability: float = Field(ge=0, le=1)
