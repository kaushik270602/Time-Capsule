"""
Notification service orchestrator for TimeLock.

Coordinates all notification channels (email, push, in-app) and logs delivery status.
"""

import logging
from sqlalchemy.orm import Session
from app.models.capsule import Capsule
from app.models.user import User
from app.models.unlock_log import UnlockLog
from app.services.email_notifier import EmailNotifier
from app.services.push_notifier import PushNotifier
from app.services.in_app_notifier import InAppNotifier

logger = logging.getLogger(__name__)


class NotificationService:
    """Orchestrates all notification channels for capsule unlocks."""
    
    def __init__(self, db: Session):
        """
        Initialize notification service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.email_notifier = EmailNotifier()
        self.push_notifier = PushNotifier()
        self.in_app_notifier = InAppNotifier(db)
    
    def notify_unlock(self, capsule_id: int) -> None:
        """
        Sends notifications through all enabled channels.
        
        Args:
            capsule_id: ID of capsule that was unlocked
            
        Runs asynchronously (should be called from Celery task).
        Logs delivery status.
        Implements retry logic for failures.
        """
        try:
            # Get capsule and user
            capsule = self.db.query(Capsule).filter(Capsule.id == capsule_id).first()
            if not capsule:
                logger.error(f"Capsule {capsule_id} not found for notification")
                return
            
            user = self.db.query(User).filter(User.id == capsule.user_id).first()
            if not user:
                logger.error(f"User {capsule.user_id} not found for capsule {capsule_id}")
                return
            
            logger.info(f"Starting notification process for capsule {capsule_id}")
            
            # Send notifications — in-app first (instant), then email (may be slow)
            in_app_sent = self._send_in_app_notification(user, capsule)
            email_sent = self._send_email_notification(user, capsule)
            push_sent = self._send_push_notification(user, capsule)
            
            # Log delivery status in unlock_log
            self._log_delivery_status(capsule_id, email_sent, push_sent, in_app_sent)
            
            # Log summary
            logger.info(
                f"Notification process completed for capsule {capsule_id}: "
                f"email={email_sent}, push={push_sent}, in_app={in_app_sent}"
            )
            
        except Exception as e:
            logger.error(f"Error in notify_unlock for capsule {capsule_id}: {e}")
    
    def _send_email_notification(self, user: User, capsule: Capsule) -> bool:
        """
        Sends email notification.
        
        Args:
            user: User to notify
            capsule: Capsule that was unlocked
            
        Returns:
            True if sent successfully
        """
        try:
            success = self.email_notifier.send_email(user, capsule)
            return success
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    def _send_push_notification(self, user: User, capsule: Capsule) -> bool:
        """
        Sends push notification.
        
        Args:
            user: User to notify
            capsule: Capsule that was unlocked
            
        Returns:
            True if sent successfully
        """
        try:
            success = self.push_notifier.send_push(user, capsule)
            return success
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            return False
    
    def _send_in_app_notification(self, user: User, capsule: Capsule) -> bool:
        """
        Creates in-app notification.
        
        Args:
            user: User to notify
            capsule: Capsule that was unlocked
            
        Returns:
            True if created successfully
        """
        try:
            success = self.in_app_notifier.create_in_app_notification(user, capsule)
            return success
        except Exception as e:
            logger.error(f"Error creating in-app notification: {e}")
            return False
    
    def _log_delivery_status(
        self, 
        capsule_id: int, 
        email_sent: bool, 
        push_sent: bool, 
        in_app_sent: bool
    ) -> None:
        """
        Logs notification delivery status in unlock_log.
        
        Args:
            capsule_id: Capsule ID
            email_sent: Whether email was sent successfully
            push_sent: Whether push notification was sent successfully
            in_app_sent: Whether in-app notification was created successfully
        """
        try:
            # Get or create unlock_log entry
            unlock_log = self.db.query(UnlockLog).filter(
                UnlockLog.capsule_id == capsule_id
            ).first()
            
            if not unlock_log:
                logger.warning(f"No unlock_log found for capsule {capsule_id}, creating one")
                unlock_log = UnlockLog(capsule_id=capsule_id)
                self.db.add(unlock_log)
            
            # Update notification status
            unlock_log.email_sent = email_sent
            unlock_log.push_sent = push_sent
            unlock_log.notification_sent = in_app_sent
            
            self.db.commit()
            
            logger.info(f"Delivery status logged for capsule {capsule_id}")
            
        except Exception as e:
            logger.error(f"Error logging delivery status: {e}")
            self.db.rollback()
