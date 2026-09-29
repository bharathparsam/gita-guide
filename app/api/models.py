from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.classification import ClassificationResult
from app.models.conversation import ConversationContext
from app.models.generation import GuidanceResponse as GroundedGuidance


class ClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=4_000)


class ClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    client_request_id: str | None = None
    classification: ClassificationResult


class GuidanceRequest(ClassificationRequest):
    conversation: ConversationContext = Field(default_factory=ConversationContext)


class GuidanceApiResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    client_request_id: str | None = None
    result: GroundedGuidance
    conversation: ConversationContext
    summary_updated: bool
    summary_deferred: bool = False
    summarized_turn_count: int = Field(default=0, ge=0)


class ConversationSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation: ConversationContext


class ConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    client_request_id: str | None = None
    conversation: ConversationContext
    summary_updated: bool
    summarized_turn_count: int = Field(default=0, ge=0)


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "not_ready"]
