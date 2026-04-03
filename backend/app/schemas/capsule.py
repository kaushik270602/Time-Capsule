"""Pydantic schemas for capsule endpoints.

Requirements: 8.1, 8.2, 8.3, 8.4
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone as tz
from typing import Optional, List

from app.utils.sanitize import sanitize_input
from app.services.timezone_service import TimezoneService, InvalidTimezoneError


class AIAnalysisResponse(BaseModel):
    """Pydantic response schema for AI analysis data (Req 8.1, 8.2, 8.3, 8.4)."""
    summary: Optional[str] = None
    sentiment_label: Optional[str] = None
    sentiment_confidence: Optional[float] = None
    tone_description: Optional[str] = None
    image_analyses: Optional[List[dict]] = None
    video_summaries: Optional[List[dict]] = None
    recap_text: Optional[str] = None
    processing_status: str = "pending"
    created_at: datetime

    model_config = {"from_attributes": True}


class CapsuleCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text_content: Optional[str] = None
    unlock_date: datetime
    timezone: str = Field(default="UTC", max_length=64)
    is_public: bool = False

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        return sanitize_input(v)

    @field_validator("text_content")
    @classmethod
    def sanitize_text_content(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_input(v) if v is not None else v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validates timezone is a valid IANA identifier (Req 2.1, 2.2, 2.3)."""
        # Treat empty or None as UTC (Req 2.3)
        if not v:
            return "UTC"
        try:
            TimezoneService.validate_timezone(v)
        except InvalidTimezoneError as e:
            raise ValueError(str(e))
        return v

    @field_validator("unlock_date")
    @classmethod
    def validate_unlock_date_format(cls, v: datetime) -> datetime:
        """Ensure unlock_date is properly formatted. Future validation happens in service."""
        # Remove timezone info - we'll handle conversion in the service
        if v.tzinfo is not None:
            v = v.replace(tzinfo=None)
        return v


class CapsuleResponse(BaseModel):
    id: int
    title: str
    text_content: Optional[str] = None
    media_urls: List[str] = []
    transcriptions: List[str] = []
    unlock_date: datetime
    timezone: str = "UTC"  # IANA timezone identifier (Req 4.1)
    unlock_date_local: Optional[str] = None  # Formatted in stored timezone with abbreviation (Req 4.1, 4.3)
    status: str
    is_public: bool
    created_at: datetime
    time_until_unlock: Optional[int] = None
    user_id: Optional[int] = None
    dst_adjustment_message: Optional[str] = None  # DST adjustment info (Req 5.2)
    ai_analysis: Optional[AIAnalysisResponse] = None  # Expanded AI analysis (Req 8.1, 8.2, 8.3, 8.4)

    model_config = {"from_attributes": True}


class CapsuleListResponse(BaseModel):
    capsules: List[CapsuleResponse]
    total: int


class PublicCapsuleResponse(BaseModel):
    id: int
    title: str
    text_content: Optional[str] = None
    unlock_date: datetime
    timezone: str = "UTC"  # IANA timezone identifier
    unlock_date_local: Optional[str] = None  # Formatted in stored timezone
    created_at: datetime
    user_id: int

    model_config = {"from_attributes": True}


class PublicFeedResponse(BaseModel):
    capsules: List[PublicCapsuleResponse]
    total: int


class MediaUploadResponse(BaseModel):
    url: str
    message: str
