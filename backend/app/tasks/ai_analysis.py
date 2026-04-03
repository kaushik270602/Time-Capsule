"""
AI Analysis Celery tasks for TimeLock.

Handles async AI analysis for unlocked capsules.
"""

import logging
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ai_analysis.analyze_capsule_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def analyze_capsule_task(self, capsule_id: int) -> dict:
    """
    Performs AI analysis on an unlocked capsule.
    
    This task:
    1. Creates AIService instance
    2. Calls analyze_capsule() to generate summary and transcriptions
    3. Handles failures with retry logic
    
    Args:
        self: Celery task instance (bound)
        capsule_id: ID of capsule to analyze
    
    Returns:
        Dictionary with analysis result
    """
    db = SessionLocal()
    
    try:
        logger.info(f"Starting AI analysis task for capsule {capsule_id}")
        
        # Create AI service and perform analysis
        ai_service = AIService()
        ai_analysis = ai_service.analyze_capsule(capsule_id, db)
        
        if ai_analysis:
            logger.info(f"Successfully completed AI analysis for capsule {capsule_id}")
            
            return {
                "status": "success",
                "capsule_id": capsule_id,
                "analysis_id": ai_analysis.id,
                "has_summary": ai_analysis.summary is not None,
                "processing_status": ai_analysis.processing_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            logger.warning(f"AI analysis returned None for capsule {capsule_id}")
            
            return {
                "status": "failed",
                "capsule_id": capsule_id,
                "processing_status": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error in analyze_capsule_task for capsule {capsule_id}: {e}")
        
        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except Exception as retry_error:
            logger.error(f"Failed to schedule retry: {retry_error}")
            
            return {
                "status": "error",
                "capsule_id": capsule_id,
                "processing_status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    finally:
        db.close()
