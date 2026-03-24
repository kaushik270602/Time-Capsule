from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class ProfileResponse(BaseModel):
    id: int
    email: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    """Update non-sensitive profile fields. Currently a placeholder for future fields."""
    pass


class EmailChangeRequest(BaseModel):
    """Change email — requires current password for re-authentication (Req 2.4)."""
    new_email: EmailStr
    current_password: str = Field(min_length=1)
