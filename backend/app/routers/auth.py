from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    VerifyEmailRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    TokenResponse,
    UserResponse,
    MessageResponse,
)
from app.services.auth_service import (
    AuthService,
    EmailAlreadyExistsError,
    InvalidEmailError,
    InvalidCredentialsError,
    UnverifiedEmailError,
    UserNotFoundError,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    auth = AuthService(db)
    try:
        user = auth.register_user(body.email, body.password)
    except EmailAlreadyExistsError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except InvalidEmailError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")
    return user


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify user email address using a token."""
    auth = AuthService(db)
    auth.verify_email(body.token)
    return MessageResponse(message="Email verified successfully")


@router.post("/login", response_model=TokenResponse)
def login(body: UserLoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate user and return a JWT token. Also sets an httpOnly cookie."""
    auth = AuthService(db)
    try:
        user, token = auth.login(body.email, body.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    except UnverifiedEmailError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

    is_production = not settings.DEBUG
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=settings.JWT_EXPIRATION_HOURS * 3600,
        path="/",
    )
    return TokenResponse(access_token=token)


@router.post("/password-reset-request", response_model=MessageResponse)
def password_reset_request(body: PasswordResetRequest, db: Session = Depends(get_db)):
    """Request a password reset email."""
    auth = AuthService(db)
    try:
        auth.request_password_reset(body.email)
    except UserNotFoundError:
        # Don't reveal whether the email exists — always return success
        pass
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/password-reset", response_model=MessageResponse)
def password_reset(body: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Reset password using a reset token."""
    auth = AuthService(db)
    auth.reset_password(body.token, body.new_password)
    return MessageResponse(message="Password reset successfully")


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return current_user

@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    """Clear the httpOnly auth cookie."""
    is_production = not settings.DEBUG
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        path="/",
    )
    return MessageResponse(message="Logged out successfully")
