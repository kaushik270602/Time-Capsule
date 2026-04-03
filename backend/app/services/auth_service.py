from sqlalchemy.orm import Session
from app.models.user import User
from app.utils.password import PasswordHasher
from app.utils.jwt import JWTManager
import re
from typing import Tuple


class EmailAlreadyExistsError(Exception):
    """Raised when email already exists"""
    pass


class InvalidEmailError(Exception):
    """Raised when email format is invalid"""
    pass


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid"""
    pass


class UnverifiedEmailError(Exception):
    """Raised when user email is not verified"""
    pass


class UserNotFoundError(Exception):
    """Raised when user is not found"""
    pass


class AuthService:
    """Handles user authentication operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.password_hasher = PasswordHasher()
        self.jwt_manager = JWTManager()
    
    @staticmethod
    def _validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def register_user(self, email: str, password: str) -> User:
        """
        Create new user account with hashed password.
        
        Args:
            email: User email address
            password: Plain text password
            
        Returns:
            Created User object
            
        Raises:
            EmailAlreadyExistsError: If email already registered
            InvalidEmailError: If email format is invalid
        """
        # Validate email format
        if not self._validate_email(email):
            raise InvalidEmailError("Invalid email format")
        
        # Check if email already exists
        existing_user = self.db.query(User).filter(User.email == email).first()
        if existing_user:
            raise EmailAlreadyExistsError("Email already registered")
        
        # Hash password
        password_hash = self.password_hasher.hash_password(password)
        
        # Create user
        user = User(
            email=email,
            password_hash=password_hash,
            is_verified=False
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # Auto-verify in debug mode (no SMTP configured)
        from app.config import settings
        if settings.DEBUG:
            user.is_verified = True
            self.db.commit()
            self.db.refresh(user)
        
        # TODO: Send verification email in production
        
        return user
    
    def verify_email(self, token: str) -> bool:
        """
        Mark user account as verified.
        
        Args:
            token: Verification token
            
        Returns:
            True if successful
            
        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token has expired
        """
        # TODO: Implement token-based email verification
        # For now, this is a placeholder
        return True
    
    def login(self, email: str, password: str) -> Tuple[User, str]:
        """
        Validate credentials and return User and JWT token.
        
        Args:
            email: User email
            password: Plain text password
            
        Returns:
            Tuple of (User object, JWT token)
            
        Raises:
            InvalidCredentialsError: If credentials are invalid
            UnverifiedEmailError: If email not verified
        """
        # Find user by email
        user = self.db.query(User).filter(User.email == email).first()
        
        if not user:
            raise InvalidCredentialsError("Invalid email or password")
        
        # Verify password
        if not self.password_hasher.verify_password(password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")
        
        # Check if email is verified
        if not user.is_verified:
            raise UnverifiedEmailError("Email not verified")
        
        # Create JWT token
        token = self.jwt_manager.create_token(user.id)
        
        return user, token
    
    def request_password_reset(self, email: str) -> None:
        """
        Send password reset email with token.
        
        Args:
            email: User email address
            
        Raises:
            UserNotFoundError: If user not found
        """
        user = self.db.query(User).filter(User.email == email).first()
        
        if not user:
            raise UserNotFoundError("User not found")
        
        # TODO: Generate reset token and send email
        pass
    
    def reset_password(self, token: str, new_password: str) -> bool:
        """
        Update user password with new hash.
        
        Args:
            token: Password reset token
            new_password: New plain text password
            
        Returns:
            True if successful
            
        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token has expired
        """
        # TODO: Validate token and update password
        # For now, this is a placeholder
        return True
