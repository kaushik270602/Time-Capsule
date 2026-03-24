from datetime import datetime, timezone
from app.models.capsule import Capsule
from typing import Dict, Optional


class AccessDeniedError(Exception):
    """Raised when access to capsule is denied"""
    pass


class LockingMechanism:
    """Enforces time-based access control for capsules"""
    
    @staticmethod
    def is_locked(capsule: Capsule) -> bool:
        """
        Check if capsule is locked.
        
        Args:
            capsule: Capsule object
            
        Returns:
            True if capsule is locked
        """
        # Status is the source of truth - if status is "unlocked", capsule is unlocked
        # The scheduler sets status to "unlocked" when unlock_date is reached
        if capsule.status == "unlocked":
            return False
        
        # If status is "locked", capsule is locked
        return True
    
    @staticmethod
    def can_access_content(capsule: Capsule, user_id: Optional[int]) -> bool:
        """
        Check if user can access capsule content.
        
        Args:
            capsule: Capsule object
            user_id: Requesting user ID (None for unauthenticated)
            
        Returns:
            True if user can access content
        """
        # Check if capsule is locked
        if LockingMechanism.is_locked(capsule):
            return False
        
        # Check ownership for private capsules
        if not capsule.is_public:
            if user_id is None or user_id != capsule.user_id:
                return False
        
        # Public unlocked capsules are accessible to all
        return True
    
    @staticmethod
    def get_content_or_deny(capsule: Capsule, user_id: Optional[int]) -> Dict:
        """
        Return capsule content if access allowed, metadata only if locked.
        
        Args:
            capsule: Capsule object
            user_id: Requesting user ID
            
        Returns:
            Dictionary with capsule data
            
        Raises:
            AccessDeniedError: If unauthorized
        """
        # Check if locked
        is_locked = LockingMechanism.is_locked(capsule)
        
        # For locked capsules, check ownership
        if is_locked:
            if user_id is None or user_id != capsule.user_id:
                raise AccessDeniedError("Cannot access locked capsule")
            
            # Owner can see metadata but not content
            return {
                "id": capsule.id,
                "title": capsule.title,
                "unlock_date": capsule.unlock_date,
                "status": capsule.status,
                "is_public": capsule.is_public,
                "created_at": capsule.created_at,
                "text_content": None,
                "media_urls": [],
                "transcriptions": []
            }
        
        # For unlocked capsules, check access rights
        if not LockingMechanism.can_access_content(capsule, user_id):
            raise AccessDeniedError("Access denied to this capsule")
        
        # Return full content
        return {
            "id": capsule.id,
            "user_id": capsule.user_id,
            "title": capsule.title,
            "text_content": capsule.text_content,
            "media_urls": capsule.media_urls,
            "transcriptions": capsule.transcriptions,
            "unlock_date": capsule.unlock_date,
            "status": capsule.status,
            "is_public": capsule.is_public,
            "created_at": capsule.created_at
        }
