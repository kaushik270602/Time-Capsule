"""
Unlock orchestrator for TimeLock.

Coordinates the complete unlock workflow including status updates, logging,
AI analysis, and notifications with transaction handling and retry logic.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.capsule import Capsule
from app.models.unlock_log import UnlockLog
from app.database import SessionLocal
from app.cache import invalidate_capsule_caches

logger = logging.getLogger(__name__)


class UnlockOrchestrator:
    """Orchestrates the complete capsule unlock workflow."""
    
    def process_unlock(self, capsule_id: int, db: Optional[Session] = None) -> bool:
        """
        Orchestrates complete unlock workflow with transaction handling.
        
        Workflow steps:
        1. Update capsule status to "unlocked"
        2. Create unlock log entry
        3. Trigger AI analysis (async via Celery)
        4. Send notifications (async via Celery)
        
        Args:
            capsule_id: ID of capsule to unlock
            db: Optional database session (creates new if not provided)
        
        Returns:
            True if unlock successful, False otherwise
        
        Note:
            Uses database transaction for atomicity.
            AI analysis and notifications are triggered asynchronously.
        """
        # Create database session if not provided
        should_close_db = False
        if db is None:
            db = SessionLocal()
            should_close_db = True
        
        try:
            # Start transaction
            logger.info(f"Starting unlock process for capsule {capsule_id}")
            
            # Get capsule with row lock to prevent concurrent unlocks
            capsule = db.query(Capsule).filter(
                Capsule.id == capsule_id
            ).with_for_update().first()
            
            if not capsule:
                logger.error(f"Capsule {capsule_id} not found")
                return False
            
            # Check if already unlocked
            if capsule.status == "unlocked":
                logger.info(f"Capsule {capsule_id} already unlocked, skipping")
                return True
            
            # Verify unlock date has arrived
            current_time = datetime.now(timezone.utc)
            if capsule.unlock_date > current_time:
                logger.warning(
                    f"Capsule {capsule_id} unlock date {capsule.unlock_date} "
                    f"has not arrived yet (current: {current_time})"
                )
                return False
            
            # Update capsule status
            capsule.status = "unlocked"
            capsule.updated_at = current_time
            
            # Create unlock log entry
            unlock_log = UnlockLog(
                capsule_id=capsule_id,
                unlocked_at=current_time,
                notification_sent=False,
                email_sent=False,
                push_sent=False
            )
            db.add(unlock_log)
            
            # Commit transaction
            db.commit()
            
            logger.info(f"Successfully unlocked capsule {capsule_id}")
            
            # Invalidate caches for the capsule owner
            invalidate_capsule_caches(capsule.user_id)
            
            # Trigger async tasks (outside transaction)
            self._trigger_ai_analysis(capsule_id)
            self._trigger_notifications(capsule_id)
            
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error during unlock of capsule {capsule_id}: {e}")
            db.rollback()
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error during unlock of capsule {capsule_id}: {e}")
            db.rollback()
            return False
            
        finally:
            if should_close_db:
                db.close()
    
    def retry_failed_unlock(self, capsule_id: int, attempt: int) -> None:
        """
        Retries unlock with exponential backoff.
        
        Args:
            capsule_id: ID of capsule to retry
            attempt: Current retry attempt number (1-based)
        
        Note:
            Max 3 attempts.
            Logs failures for manual intervention.
            Uses exponential backoff: 60s, 120s, 240s
        """
        max_attempts = 3
        
        if attempt > max_attempts:
            logger.error(
                f"Max retry attempts ({max_attempts}) reached for capsule {capsule_id}. "
                f"Manual intervention required."
            )
            return
        
        logger.info(f"Retrying unlock for capsule {capsule_id}, attempt {attempt}/{max_attempts}")
        
        # Calculate backoff delay (exponential: 60s, 120s, 240s)
        backoff_delay = 60 * (2 ** (attempt - 1))
        
        # Import here to avoid circular dependency
        from app.tasks.unlock_scheduler import unlock_capsule
        
        # Schedule retry with delay
        unlock_capsule.apply_async(
            args=[capsule_id],
            countdown=backoff_delay,
            retry=False  # Don't use Celery's auto-retry, we handle it manually
        )
        
        logger.info(
            f"Scheduled retry for capsule {capsule_id} in {backoff_delay} seconds "
            f"(attempt {attempt}/{max_attempts})"
        )
    
    def _trigger_ai_analysis(self, capsule_id: int) -> None:
        """
        Triggers AI analysis as async Celery task.
        
        Args:
            capsule_id: ID of capsule to analyze
        """
        try:
            # Import here to avoid circular dependency
            from app.tasks.ai_analysis import analyze_capsule_task
            
            # Trigger async task
            analyze_capsule_task.apply_async(
                args=[capsule_id],
                retry=True,
                retry_policy={
                    'max_retries': 3,
                    'interval_start': 60,
                    'interval_step': 60,
                    'interval_max': 300,
                }
            )
            
            logger.info(f"Triggered AI analysis task for capsule {capsule_id}")
            
        except Exception as e:
            logger.error(f"Failed to trigger AI analysis for capsule {capsule_id}: {e}")
    
    def _trigger_notifications(self, capsule_id: int) -> None:
        """
        Triggers notifications as async Celery task.
        
        Args:
            capsule_id: ID of capsule to send notifications for
        """
        try:
            # Import here to avoid circular dependency
            from app.tasks.notifications import send_unlock_notification
            
            # Trigger async task
            send_unlock_notification.apply_async(
                args=[capsule_id],
                retry=True,
                retry_policy={
                    'max_retries': 3,
                    'interval_start': 30,
                    'interval_step': 30,
                    'interval_max': 180,
                }
            )
            
            logger.info(f"Triggered notification task for capsule {capsule_id}")
            
        except Exception as e:
            logger.error(f"Failed to trigger notifications for capsule {capsule_id}: {e}")
