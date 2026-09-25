from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.classification import ClassificationResult
from app.models.retrieval import RetrievedChunk


class GroundedGenerationInput(BaseModel):
    """The only input contract accepted by the future guidance generator."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: str
    message: str = Field(min_length=1, max_length=4_000)
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


class GuidanceResponse(BaseModel):
    """Citation-checked, output-filtered guidance returned by the generator."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    request_id: str
    guidance: str = Field(min_length=1)
    citations: tuple[str, ...] = Field(min_length=1, max_length=5)
    grounded_chunk_ids: tuple[str, ...] = Field(min_length=1, max_length=5)
    model: str
    provider_request_id: str | None = None
    langchain_run_id: str | None = None
