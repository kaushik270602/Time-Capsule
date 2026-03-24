import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.capsule import Capsule
from app.models.ai_analysis import AIAnalysis
from app.services.transcription_service import TranscriptionService
from app.services.summary_generator import SummaryGenerator

logger = logging.getLogger(__name__)


class AIService:
    """Orchestrator service for all AI operations on capsules."""
    
    def __init__(self):
        self.transcription_service = TranscriptionService()
        self.summary_generator = SummaryGenerator()
    
    def analyze_capsule(self, capsule_id: int, db: Session) -> Optional[AIAnalysis]:
        """
        Performs AI analysis on an unlocked capsule.
        
        This method:
        1. Retrieves the capsule from the database
        2. Transcribes any audio/video media (if not already transcribed)
        3. Generates a summary using GPT-4
        4. Stores the results in the AI_Analysis table
        
        Args:
            capsule_id: ID of the capsule to analyze
            db: Database session
        
        Returns:
            AIAnalysis object if successful, None if analysis fails
        
        Note:
            Failures are handled gracefully - the capsule remains accessible
            even if AI analysis fails. Errors are logged for manual review.
        """
        try:
            # Retrieve the capsule
            capsule = db.query(Capsule).filter(Capsule.id == capsule_id).first()
            
            if not capsule:
                logger.error(f"Capsule {capsule_id} not found for AI analysis")
                return None
            
            if capsule.status != "unlocked":
                logger.warning(f"Attempted AI analysis on locked capsule {capsule_id}")
                return None
            
            logger.info(f"Starting AI analysis for capsule {capsule_id}")
            
            # Transcribe media files if needed
            transcriptions = list(capsule.transcriptions) if capsule.transcriptions else []
            media_urls = capsule.media_urls if capsule.media_urls else []
            
            # Only transcribe if we have media and no transcriptions yet
            if media_urls and len(transcriptions) < len(media_urls):
                logger.info(f"Transcribing {len(media_urls)} media files")
                for media_url in media_urls:
                    # Determine media type from URL extension
                    media_type = self._get_media_type(media_url)
                    
                    if media_type in ['audio', 'video']:
                        transcription = self.transcription_service.transcribe_media(
                            media_url=media_url,
                            media_type=media_type
                        )
                        
                        if transcription:
                            transcriptions.append(transcription)
                        else:
                            logger.warning(f"Failed to transcribe media: {media_url}")
                
                # Update capsule with transcriptions
                if transcriptions:
                    capsule.transcriptions = transcriptions
                    db.commit()
                    logger.info(f"Stored {len(transcriptions)} transcriptions for capsule {capsule_id}")
            
            # Generate summary
            summary = self.summary_generator.generate_summary(
                text_content=capsule.text_content or "",
                transcriptions=transcriptions,
                created_at=capsule.created_at,
                unlocked_at=datetime.now(timezone.utc)
            )
            
            if not summary:
                logger.warning(f"Failed to generate summary for capsule {capsule_id}")
                # Still create AI analysis record with None summary
            
            # Store AI analysis
            ai_analysis = AIAnalysis(
                capsule_id=capsule_id,
                summary=summary
            )
            
            db.add(ai_analysis)
            db.commit()
            db.refresh(ai_analysis)
            
            logger.info(f"Successfully completed AI analysis for capsule {capsule_id}")
            return ai_analysis
            
        except Exception as e:
            logger.error(f"Error during AI analysis for capsule {capsule_id}: {e}")
            db.rollback()
            return None
    
    def _get_media_type(self, media_url: str) -> str:
        """
        Determines media type from URL extension.
        
        Args:
            media_url: URL of the media file
        
        Returns:
            'audio', 'video', or 'image'
        """
        url_lower = media_url.lower()
        
        # Audio formats
        if any(url_lower.endswith(ext) for ext in ['.mp3', '.wav', '.m4a']):
            return 'audio'
        
        # Video formats
        if any(url_lower.endswith(ext) for ext in ['.mp4', '.mov', '.avi']):
            return 'video'
        
        # Image formats
        if any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            return 'image'
        
        return 'unknown'

