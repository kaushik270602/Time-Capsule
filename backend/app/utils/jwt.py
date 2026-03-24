from datetime import datetime, timedelta
from typing import Optional
import jwt
from app.config import settings


class InvalidTokenError(Exception):
    """Raised when token is invalid"""
    pass


class ExpiredTokenError(Exception):
    """Raised when token has expired"""
    pass


class JWTManager:
    """Handles JWT token creation and validation"""
    
    @staticmethod
    def create_token(user_id: int, expiration_hours: int = None) -> str:
        """
        Create a JWT token with user_id claim and expiration.
        
        Args:
            user_id: User ID to encode in token
            expiration_hours: Hours until token expires (default from settings)
            
        Returns:
            Encoded JWT token string
        """
        if expiration_hours is None:
            expiration_hours = settings.JWT_EXPIRATION_HOURS
            
        expiration = datetime.utcnow() + timedelta(hours=expiration_hours)
        
        payload = {
            "user_id": user_id,
            "exp": expiration,
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        
        return token
    
    @staticmethod
    def validate_token(token: str) -> int:
        """
        Validate token signature and expiration.
        
        Args:
            token: JWT token to validate
            
        Returns:
            user_id from token claims
            
        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token has expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("user_id")
            
            if user_id is None:
                raise InvalidTokenError("Token missing user_id claim")
                
            return user_id
            
        except jwt.ExpiredSignatureError:
            raise ExpiredTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {str(e)}")
