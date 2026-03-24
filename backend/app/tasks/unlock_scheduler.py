"""
Unlock scheduler Celery tasks for TimeLock.

Implements periodic task to check and unlock capsules when their unlock date arrives.
"""

import logging
from datetime import datetime, timezone
from typing import List

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.capsule import Capsule
from app.services.unlock_orchestrator import UnlockOrchestrator

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.unlock_scheduler.check_and_unlock_capsules")
def check_and_unlock_capsules() -> dict:
    """
    Periodic task that checks for capsules ready to unlock.
    
    This task:
    1. Queries capsules where unlock_date <= now AND status = "locked"
    2. Processes unlocks in order by unlock_date (earliest first)
    3. Calls unlock_capsule task for each capsule
    
    Runs every minute (configured in celery_app.py beat_schedule).
    
    Returns:
        Dictionary with task execution summary
    """
    db = SessionLocal()
    
    try:
        current_time = datetime.now(timezone.utc)
        
        logger.info(f"Starting unlock check at {current_time}")
        
        # Query capsules ready to unlock
        # Order by unlock_date to ensure fairness (earliest first)
        capsules_to_unlock = db.query(Capsule).filter(
            Capsule.status == "locked",
            Capsule.unlock_date <= current_time
        ).order_by(Capsule.unlock_date.asc()).all()
        
        capsule_count = len(capsules_to_unlock)
        
        if capsule_count == 0:
            logger.info("No capsules ready to unlock")
            return {
                "status": "success",
                "capsules_found": 0,
                "capsules_processed": 0,
                "timestamp": current_time.isoformat()
            }
        
        logger.info(f"Found {capsule_count} capsule(s) ready to unlock")
        
        # Process each capsule
        processed_count = 0
        failed_count = 0
        
        for capsule in capsules_to_unlock:
            try:
                logger.info(
                    f"Processing capsule {capsule.id} "
                    f"(unlock_date: {capsule.unlock_date}, title: {capsule.title})"
                )
                
                # Trigger unlock task for this capsule
                unlock_capsule.apply_async(
                    args=[capsule.id],
                    retry=False  # We handle retries manually in the task
                )
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error queuing unlock for capsule {capsule.id}: {e}")
                failed_count += 1
        
        logger.info(
            f"Unlock check completed: {processed_count} queued, {failed_count} failed"
        )
        
        return {
            "status": "success",
            "capsules_found": capsule_count,
            "capsules_processed": processed_count,
            "capsules_failed": failed_count,
            "timestamp": current_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in check_and_unlock_capsules: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.unlock_scheduler.unlock_capsule",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def unlock_capsule(self, capsule_id: int, attempt: int = 1) -> dict:
    """
    Unlocks a specific capsule.
    
    This task:
    1. Calls UnlockOrchestrator.process_unlock()
    2. Handles failures with retry logic
    3. Logs all unlock attempts
    
    Args:
        self: Celery task instance (bound)
        capsule_id: ID of capsule to unlock
        attempt: Current attempt number (for manual retry tracking)
    
    Returns:
        Dictionary with unlock result
    """
    logger.info(f"Unlock task started for capsule {capsule_id} (attempt {attempt})")
    
    orchestrator = UnlockOrchestrator()
    
    try:
        # Process the unlock
        success = orchestrator.process_unlock(capsule_id)
        
        if success:
            logger.info(f"Successfully unlocked capsule {capsule_id}")
            return {
                "status": "success",
                "capsule_id": capsule_id,
                "attempt": attempt,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            # Unlock failed, retry if attempts remaining
            logger.warning(f"Failed to unlock capsule {capsule_id}, attempt {attempt}")
            
            if attempt < 3:
                # Schedule manual retry with exponential backoff
                orchestrator.retry_failed_unlock(capsule_id, attempt + 1)
                
                return {
                    "status": "failed_retry_scheduled",
                    "capsule_id": capsule_id,
                    "attempt": attempt,
                    "next_attempt": attempt + 1,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                # Max retries reached
                logger.error(
                    f"Failed to unlock capsule {capsule_id} after {attempt} attempts. "
                    f"Manual intervention required."
                )
                
                return {
                    "status": "failed_max_retries",
                    "capsule_id": capsule_id,
                    "attempt": attempt,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
    
    except Exception as e:
        logger.error(f"Exception in unlock_capsule task for capsule {capsule_id}: {e}")
        
        # Retry with Celery's built-in retry mechanism
        if attempt < 3:
            try:
                # Use exponential backoff
                countdown = 60 * (2 ** (attempt - 1))
                raise self.retry(exc=e, countdown=countdown)
            except Exception as retry_error:
                logger.error(f"Failed to schedule retry: {retry_error}")
        
        return {
            "status": "error",
            "capsule_id": capsule_id,
            "attempt": attempt,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
