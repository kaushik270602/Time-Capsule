"""Pydantic schemas for notification endpoints."""

from pydantic import BaseModel
from datetime import datetime
from typing import List


class NotificationResponse(BaseModel):
    id: int
    capsule_id: int
    message: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    total: int
