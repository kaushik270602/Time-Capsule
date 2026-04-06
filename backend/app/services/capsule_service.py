from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timezone
from app.models.capsule import Capsule
from app.services.locking_mechanism import LockingMechanism, AccessDeniedError
from app.services.timezone_service import (
    TimezoneService,
    InvalidTimezoneError,
    NonexistentTimeError,
)
from app.services.storage_adapter import StorageAdapter
from typing import List, Optional, Tuple


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
        self.timezone_service = TimezoneService()
        self.storage = StorageAdapter()
    
    def _sign_media_urls(self, urls: List[str], capsule_id: int = None) -> List[str]:
        """Convert raw S3 URLs to signed S3 URLs for direct browser access."""
        if not urls:
            return []
        result = []
        for url in urls:
            if self.storage.use_s3 and ".amazonaws.com/" in url:
                try:
                    key = url.split(".amazonaws.com/", 1)[1]
                    signed = self.storage.generate_signed_url(key)
                    result.append(signed)
                except (IndexError, Exception):
                    result.append(url)
            else:
                result.append(url)
        return result
    
    def _format_unlock_date_local(self, utc_datetime: datetime, tz_str: str) -> str:
        """
        Format unlock date in the stored timezone with abbreviation.
        
        Args:
            utc_datetime: UTC datetime
            tz_str: IANA timezone identifier
            
        Returns:
            Formatted string like "Dec 25, 2024 9:00 AM EST"
        """
        try:
            local_dt = TimezoneService.convert_from_utc(utc_datetime, tz_str)
            abbrev = TimezoneService.get_timezone_abbreviation(local_dt, tz_str)
            # Format: "Dec 25, 2024 9:00 AM EST"
            return local_dt.strftime("%b %d, %Y %-I:%M %p") + f" {abbrev}"
        except (InvalidTimezoneError, Exception):
            # Fallback to UTC display if timezone is invalid
            return utc_datetime.strftime("%b %d, %Y %-I:%M %p") + " UTC"
    
    def create_capsule(
        self,
        user_id: int,
        title: str,
        text_content: Optional[str],
        unlock_date: datetime,
        tz_str: str = "UTC",
        is_public: bool = False,
        media_urls: List[str] = None
    ) -> Tuple[Capsule, Optional[str]]:
        """
        Create new capsule with timezone-aware unlock date.
        
        Args:
            user_id: Owner user ID
            title: Capsule title
            text_content: Text message
            unlock_date: Local unlock datetime (naive)
            tz_str: IANA timezone identifier for unlock_date
            is_public: Public visibility flag
            media_urls: List of media URLs
            
        Returns:
            Tuple of (Created Capsule object, Optional DST adjustment message)
            
        Raises:
            InvalidUnlockDateError: If unlock_date not in future (after UTC conversion)
            InvalidTimezoneError: If timezone is not valid IANA identifier
            ValidationError: If validation fails
        """
        # Validate title
        if not title or not title.strip():
            raise ValidationError("Title is required")
        
        # Default to UTC if timezone is empty (Req 2.3)
        if not tz_str:
            tz_str = "UTC"
        
        # Validate timezone (Req 2.1, 2.2)
        try:
            TimezoneService.validate_timezone(tz_str)
        except InvalidTimezoneError:
            raise
        
        # Handle DST adjustment for nonexistent times (Req 5.2)
        dst_adjustment_message = None
        adjusted_datetime, was_adjusted = TimezoneService.adjust_nonexistent_time(
            unlock_date, tz_str
        )
        
        if was_adjusted:
            dst_adjustment_message = (
                f"The time {unlock_date.strftime('%Y-%m-%d %H:%M')} does not exist in {tz_str} "
                f"due to daylight saving time. Adjusted to {adjusted_datetime.strftime('%Y-%m-%d %H:%M')}."
            )
            unlock_date = adjusted_datetime
        
        # Convert local datetime to UTC (Req 1.4, 2.4)
        try:
            utc_unlock_date = TimezoneService.convert_to_utc(unlock_date, tz_str)
        except NonexistentTimeError as e:
            # This shouldn't happen after adjustment, but handle it just in case
            raise InvalidUnlockDateError(str(e))
        
        # Validate unlock_date is in future after UTC conversion (Req 2.5)
        current_time = datetime.now(timezone.utc)
        if utc_unlock_date <= current_time:
            raise InvalidUnlockDateError(
                f"Unlock date must be in the future. The selected time converts to "
                f"{utc_unlock_date.strftime('%Y-%m-%d %H:%M:%S')} UTC which has already passed."
            )
        
        # Create capsule with timezone stored (Req 3.1, 3.2)
        capsule = Capsule(
            user_id=user_id,
            title=title.strip(),
            text_content=text_content,
            unlock_date=utc_unlock_date,
            timezone=tz_str,
            status="locked",
            is_public=is_public,
            media_urls=media_urls or [],
            transcriptions=[]
        )
        
        self.db.add(capsule)
        self.db.commit()
        self.db.refresh(capsule)
        
        return capsule, dst_adjustment_message
    
    def get_capsule(self, capsule_id: int, requesting_user_id: Optional[int]) -> dict:
        """
        Retrieve capsule if user has access.
        
        Args:
            capsule_id: Capsule ID
            requesting_user_id: User requesting access
            
        Returns:
            Capsule data dictionary with timezone info and ai_analysis
            
        Raises:
            CapsuleNotFoundError: If capsule not found
            AccessDeniedError: If access denied
        """
        capsule = self.db.query(Capsule).filter(Capsule.id == capsule_id).first()
        
        if not capsule:
            raise CapsuleNotFoundError("Capsule not found")
        
        # Use locking mechanism to get content or deny
        data = self.locking.get_content_or_deny(capsule, requesting_user_id)
        
        # Add timezone fields (Req 4.1, 4.2, 4.3)
        tz_str = capsule.timezone or "UTC"
        data["timezone"] = tz_str
        data["unlock_date_local"] = self._format_unlock_date_local(capsule.unlock_date, tz_str)
        
        # Sign media URLs for browser access
        if data.get("media_urls"):
            data["media_urls"] = self._sign_media_urls(data["media_urls"], capsule_id=capsule.id)
        
        # Include ai_analysis in response (Req 8.1, 8.2, 8.3, 8.4)
        try:
            ai = capsule.ai_analysis
            if ai is not None:
                data["ai_analysis"] = {
                    "summary": ai.summary,
                    "sentiment_label": getattr(ai, "sentiment_label", None),
                    "sentiment_confidence": getattr(ai, "sentiment_confidence", None),
                    "tone_description": getattr(ai, "tone_description", None),
                    "image_analyses": getattr(ai, "image_analyses", None),
                    "video_summaries": getattr(ai, "video_summaries", None),
                    "recap_text": getattr(ai, "recap_text", None),
                    "processing_status": getattr(ai, "processing_status", "pending"),
                    "created_at": ai.created_at,
                }
            else:
                data["ai_analysis"] = None
        except Exception:
            data["ai_analysis"] = None
        
        return data
    
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
            List of capsule dictionaries with timezone info
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
        
        # Sort: locked capsules by nearest unlock date first, unlocked by most recent first
        query = query.order_by(Capsule.status.asc(), Capsule.unlock_date.desc())
        
        # Apply pagination
        capsules = query.limit(limit).offset(offset).all()
        
        # Return capsule data (locked capsules return metadata only)
        result = []
        for capsule in capsules:
            tz_str = capsule.timezone or "UTC"
            unlock_date_local = self._format_unlock_date_local(capsule.unlock_date, tz_str)
            
            if self.locking.is_locked(capsule):
                # Calculate time until unlock
                time_until_unlock = int((capsule.unlock_date - datetime.now(timezone.utc)).total_seconds())
                result.append({
                    "id": capsule.id,
                    "title": capsule.title,
                    "unlock_date": capsule.unlock_date,
                    "timezone": tz_str,
                    "unlock_date_local": unlock_date_local,
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
                    "media_urls": self._sign_media_urls(capsule.media_urls, capsule_id=capsule.id),
                    "unlock_date": capsule.unlock_date,
                    "timezone": tz_str,
                    "unlock_date_local": unlock_date_local,
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
            List of public capsule dictionaries with timezone info
        """
        capsules = self.db.query(Capsule).filter(
            Capsule.is_public == True,
            Capsule.status == "unlocked"
        ).order_by(
            Capsule.unlock_date.desc()
        ).limit(limit).offset(offset).all()
        
        result = []
        for capsule in capsules:
            tz_str = capsule.timezone or "UTC"
            unlock_date_local = self._format_unlock_date_local(capsule.unlock_date, tz_str)
            
            result.append({
                "id": capsule.id,
                "title": capsule.title,
                "text_content": capsule.text_content[:200] if capsule.text_content else None,  # Preview
                "unlock_date": capsule.unlock_date,
                "timezone": tz_str,
                "unlock_date_local": unlock_date_local,
                "created_at": capsule.created_at,
                "user_id": capsule.user_id
            })
        
        return result
