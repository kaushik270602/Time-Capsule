from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timezone
from app.models.capsule import Capsule
from app.services.locking_mechanism import LockingMechanism, AccessDeniedError
from typing import List, Optional


class InvalidUnlockDateError(Exception):
    """Raised when unlock date is invalid"""
    pass


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


class CapsuleNotFoundError(Exception):
    """Raised when capsule is not found"""
    pass


class CapsuleService:
    """Core business logic for capsule CRUD operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.locking = LockingMechanism()
    
    def create_capsule(
        self,
        user_id: int,
        title: str,
        text_content: Optional[str],
        unlock_date: datetime,
        is_public: bool = False,
        media_urls: List[str] = None
    ) -> Capsule:
        """
        Create new capsule with status "locked".
        
        Args:
            user_id: Owner user ID
            title: Capsule title
            text_content: Text message
            unlock_date: Future unlock datetime
            is_public: Public visibility flag
            media_urls: List of media URLs
            
        Returns:
            Created Capsule object
            
        Raises:
            InvalidUnlockDateError: If unlock_date not in future
            ValidationError: If validation fails
        """
        # Validate title
        if not title or not title.strip():
            raise ValidationError("Title is required")
        
        # Validate unlock_date is in future
        current_time = datetime.now(timezone.utc)
        if unlock_date <= current_time:
            raise InvalidUnlockDateError("Unlock date must be in the future")
        
        # Create capsule
        capsule = Capsule(
            user_id=user_id,
            title=title.strip(),
            text_content=text_content,
            unlock_date=unlock_date,
            status="locked",
            is_public=is_public,
            media_urls=media_urls or [],
            transcriptions=[]
        )
        
        self.db.add(capsule)
        self.db.commit()
        self.db.refresh(capsule)
        
        return capsule
    
    def get_capsule(self, capsule_id: int, requesting_user_id: Optional[int]) -> dict:
        """
        Retrieve capsule if user has access.
        
        Args:
            capsule_id: Capsule ID
            requesting_user_id: User requesting access
            
        Returns:
            Capsule data dictionary
            
        Raises:
            CapsuleNotFoundError: If capsule not found
            AccessDeniedError: If access denied
        """
        capsule = self.db.query(Capsule).filter(Capsule.id == capsule_id).first()
        
        if not capsule:
            raise CapsuleNotFoundError("Capsule not found")
        
        # Use locking mechanism to get content or deny
        return self.locking.get_content_or_deny(capsule, requesting_user_id)
    
    def list_user_capsules(
        self,
        user_id: int,
        filter_status: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[dict]:
        """
        Return list of user's capsules with filters applied.
        
        Args:
            user_id: User ID
            filter_status: Filter by status (locked/unlocked)
            search_query: Search in title and content
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of capsule dictionaries
        """
        query = self.db.query(Capsule).filter(Capsule.user_id == user_id)
        
        # Apply status filter
        if filter_status:
            query = query.filter(Capsule.status == filter_status)
        
        # Apply search
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                or_(
                    Capsule.title.ilike(search_pattern),
                    Capsule.text_content.ilike(search_pattern)
                )
            )
        
        # Sort by unlock_date (nearest first)
        query = query.order_by(Capsule.unlock_date.asc())
        
        # Apply pagination
        capsules = query.limit(limit).offset(offset).all()
        
        # Return capsule data (locked capsules return metadata only)
        result = []
        for capsule in capsules:
            if self.locking.is_locked(capsule):
                # Calculate time until unlock
                time_until_unlock = int((capsule.unlock_date - datetime.now(timezone.utc)).total_seconds())
                result.append({
                    "id": capsule.id,
                    "title": capsule.title,
                    "unlock_date": capsule.unlock_date,
                    "status": capsule.status,
                    "is_public": capsule.is_public,
                    "created_at": capsule.created_at,
                    "time_until_unlock": max(0, time_until_unlock)
                })
            else:
                result.append({
                    "id": capsule.id,
                    "title": capsule.title,
                    "text_content": capsule.text_content,
                    "media_urls": capsule.media_urls,
                    "unlock_date": capsule.unlock_date,
                    "status": capsule.status,
                    "is_public": capsule.is_public,
                    "created_at": capsule.created_at
                })
        
        return result
    
    def get_public_feed(self, limit: int = 50, offset: int = 0) -> List[dict]:
        """
        Return recently unlocked public capsules.
        
        Args:
            limit: Maximum number of results
            offset: Pagination offset
            
        Returns:
            List of public capsule dictionaries
        """
        capsules = self.db.query(Capsule).filter(
            Capsule.is_public == True,
            Capsule.status == "unlocked"
        ).order_by(
            Capsule.unlock_date.desc()
        ).limit(limit).offset(offset).all()
        
        result = []
        for capsule in capsules:
            result.append({
                "id": capsule.id,
                "title": capsule.title,
                "text_content": capsule.text_content[:200] if capsule.text_content else None,  # Preview
                "unlock_date": capsule.unlock_date,
                "created_at": capsule.created_at,
                "user_id": capsule.user_id
            })
        
        return result
