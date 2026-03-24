"""Pydantic schemas for capsule endpoints."""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
from typing import Optional, List

from app.utils.sanitize import sanitize_input


class CapsuleCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text_content: Optional[str] = None
    unlock_date: datetime
    is_public: bool = False

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        return sanitize_input(v)

    @field_validator("text_content")
    @classmethod
    def sanitize_text_content(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_input(v) if v is not None else v

    @field_validator("unlock_date")
    @classmethod
    def validate_future_date(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        # Ensure timezone-aware
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= now:
            raise ValueError("unlock_date must be in the future")
        return v


class CapsuleResponse(BaseModel):
    id: int
    title: str
    text_content: Optional[str] = None
    media_urls: List[str] = []
    transcriptions: List[str] = []
    unlock_date: datetime
    status: str
    is_public: bool
    created_at: datetime
    time_until_unlock: Optional[int] = None
    user_id: Optional[int] = None

    model_config = {"from_attributes": True}


class CapsuleListResponse(BaseModel):
    capsules: List[CapsuleResponse]
    total: int


class PublicCapsuleResponse(BaseModel):
    id: int
    title: str
    text_content: Optional[str] = None
    unlock_date: datetime
    created_at: datetime
    user_id: int

    model_config = {"from_attributes": True}


class PublicFeedResponse(BaseModel):
    capsules: List[PublicCapsuleResponse]
    total: int


class MediaUploadResponse(BaseModel):
    url: str
    message: str
