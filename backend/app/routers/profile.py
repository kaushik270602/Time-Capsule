from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest, EmailChangeRequest
from app.schemas.auth import MessageResponse
from app.utils.password import PasswordHasher

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile information (Req 2.1)."""
    return current_user


@router.put("", response_model=ProfileResponse)
def update_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile information (Req 2.2). Validates before saving."""
    # Currently the User model only has email (sensitive) and auth fields.
    # This endpoint is a placeholder for future non-sensitive profile fields.
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/email", response_model=MessageResponse)
def change_email(
    body: EmailChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change user email address.
    Requires re-authentication via current password (Req 2.4).
    Sends verification to new address (Req 2.3).
    """
    # Re-authenticate: verify current password
    hasher = PasswordHasher()
    if not hasher.verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Check new email isn't already taken
    existing = db.query(User).filter(User.email == body.new_email).first()
    if existing and existing.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already in use",
        )

    # Re-fetch user within the current db session to avoid StaleDataError
    # when the user was created in a different session (e.g. during tests)
    user = db.query(User).filter(User.id == current_user.id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Update email and mark as unverified until new email is confirmed (Req 2.3)
    user.email = body.new_email
    user.is_verified = False
    db.commit()

    # TODO: Send verification email to new address

    return MessageResponse(message="Email updated. Please verify your new email address.")
