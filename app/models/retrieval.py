from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.classification import ClassificationResult


class RetrievedChunk(BaseModel):
    """One citation-ready Bhagavad Gita passage selected for grounding."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_id: str
    chapter: int = Field(ge=1, le=18)
    chapter_title: str
    verse_start: int = Field(ge=1)
    verse_end: int = Field(ge=1)
    verse_label: str
    speaker: str
    source_pdf_page: int = Field(ge=1)
    translation: str
    similarity_score: float = Field(ge=-1, le=1)
    rerank_score: float
    dense_rank: int = Field(ge=1)
    final_rank: int = Field(ge=1, le=5)
    validation_probability: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_verse_range(self) -> RetrievedChunk:
        if self.verse_end < self.verse_start:
            raise ValueError("verse_end cannot precede verse_start")
        return self


class RetrievalResult(BaseModel):
    """The bounded grounding context passed to the future answer generator."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    source: Literal["retriever", "cache", "singleflight"]
    cache_age_seconds: float | None = Field(default=None, ge=0)
    candidate_count: int = Field(ge=0)
    validation_rejected_count: int = Field(default=0, ge=0)
    validation_model: str
    validation_threshold: float = Field(ge=0, le=1)
    validation_provider_request_id: str | None = None
    ready_for_generation: bool
    chunks: tuple[RetrievedChunk, ...] = Field(max_length=5)

    @model_validator(mode="after")
    def validate_generation_gate(self) -> RetrievalResult:
        if not self.validation_model.strip():
            raise ValueError("validation_model cannot be empty")
        if self.ready_for_generation != bool(self.chunks):
            raise ValueError(
                "ready_for_generation must be true exactly when validated chunks exist"
            )
        return self


class GroundingContext(BaseModel):
    """Classification plus the bounded passages supplied to answer generation."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    classification: ClassificationResult
    retrieval: RetrievalResult
