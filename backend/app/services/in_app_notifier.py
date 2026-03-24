"""
In-app notification service for TimeLock.

Creates in-app notifications stored in the database.
"""

import logging
from sqlalchemy.orm import Session
from app.models.capsule import Capsule
from app.models.user import User
from app.models.notification import Notification

logger = logging.getLogger(__name__)


class InAppNotifier:
    """Handles in-app notifications for capsule unlocks."""
    
    def __init__(self, db: Session):
        """
        Initialize in-app notifier.
        
        Args:
            db: Database session
        """
        self.db = db
    
    def create_in_app_notification(self, user: User, capsule: Capsule) -> bool:
        """
        Creates notification record in database.
        
        Args:
            user: User to create notification for
            capsule: Capsule that was unlocked
            
        Returns:
            True if created successfully, False otherwise
            
        Visible in user dashboard.
        Includes capsule link and unlock timestamp.
        """
        try:
            # Create notification message
            unlock_date_str = capsule.unlock_date.strftime("%B %d, %Y at %I:%M %p UTC")
            message = f"Your capsule '{capsule.title}' has unlocked! (Unlocked on {unlock_date_str})"
            
            # Create notification record
            notification = Notification(
                user_id=user.id,
                capsule_id=capsule.id,
                message=message,
                is_read=False
            )
            
            self.db.add(notification)
            self.db.commit()
            self.db.refresh(notification)
            
            logger.info(f"In-app notification created for user {user.id}, capsule {capsule.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating in-app notification: {e}")
            self.db.rollback()
            return False
    
    def get_user_notifications(
        self, 
        user_id: int, 
        unread_only: bool = False,
        limit: int = 50
    ) -> list[Notification]:
        """
        Gets notifications for a user.
        
        Args:
            user_id: User ID to get notifications for
            unread_only: If True, only return unread notifications
            limit: Maximum number of notifications to return
            
        Returns:
            List of notifications ordered by created_at descending
        """
        try:
            query = self.db.query(Notification).filter(Notification.user_id == user_id)
            
            if unread_only:
                query = query.filter(Notification.is_read == False)
            
            notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()
            
            return notifications
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []
    
    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """
        Marks a notification as read.
        
        Args:
            notification_id: Notification ID to mark as read
            user_id: User ID (for authorization check)
            
        Returns:
            True if marked successfully, False otherwise
        """
        try:
            notification = self.db.query(Notification).filter(
                Notification.id == notification_id,
                Notification.user_id == user_id
            ).first()
            
            if not notification:
                logger.warning(f"Notification {notification_id} not found for user {user_id}")
                return False
            
            notification.is_read = True
            self.db.commit()
            
            logger.info(f"Notification {notification_id} marked as read")
            return True
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            self.db.rollback()
            return False
    
    def get_unread_count(self, user_id: int) -> int:
        """
        Gets count of unread notifications for a user.
        
        Args:
            user_id: User ID to get count for
            
        Returns:
            Count of unread notifications
        """
        try:
            count = self.db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.is_read == False
            ).count()
            
            return count
            
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0
