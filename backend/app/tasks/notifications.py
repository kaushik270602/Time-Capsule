"""
Notification Celery tasks for TimeLock.

Handles async notification delivery for capsule unlocks.
"""

import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.notifications.send_unlock_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def send_unlock_notification(self, capsule_id: int) -> dict:
    """
    Sends unlock notifications through all channels.
    
    This task:
    1. Creates NotificationService instance
    2. Calls notify_unlock() to send through all channels
    3. Handles failures with retry logic
    
    Args:
        self: Celery task instance (bound)
        capsule_id: ID of capsule that was unlocked
    
    Returns:
        Dictionary with notification result
    """
    db = SessionLocal()
    
    try:
        logger.info(f"Starting notification task for capsule {capsule_id}")
        
        # Create notification service and send notifications
        notification_service = NotificationService(db)
        notification_service.notify_unlock(capsule_id)
        
        logger.info(f"Successfully completed notification task for capsule {capsule_id}")
        
        return {
            "status": "success",
            "capsule_id": capsule_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in send_unlock_notification for capsule {capsule_id}: {e}")
        
        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
        except Exception as retry_error:
            logger.error(f"Failed to schedule retry: {retry_error}")
            
            return {
                "status": "error",
                "capsule_id": capsule_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    finally:
        db.close()
