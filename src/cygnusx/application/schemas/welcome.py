"""Authenticated welcome delivery and administrative contracts."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cygnusx.application.services.welcome.validation import Audience


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locale: Literal["zh-CN"] = "zh-CN"


class ClaimResponse(BaseModel):
    delivery_id: UUID
    reservation_expires_at: datetime
    title: str = "欢迎回来"
    message: str
    source: str
    duration_ms: int = 5000


class ImpressionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delivery_id: UUID


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audience: Audience
    target_week: date
    revision: int = Field(default=1, ge=1, le=10000)

    @field_validator("target_week")
    @classmethod
    def monday(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("target_week must be Monday")
        return value


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=1, max_length=500)


class MessageReviewRequest(ReviewRequest):
    enabled: bool
