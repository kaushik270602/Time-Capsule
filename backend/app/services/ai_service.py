import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.capsule import Capsule
from app.models.ai_analysis import AIAnalysis
from app.services.transcription_service import TranscriptionService
from app.services.summary_generator import SummaryGenerator
from app.services.sentiment_detector import SentimentDetector
from app.services.vision_analyzer import VisionAnalyzer
from app.services.recap_generator import RecapGenerator

logger = logging.getLogger(__name__)


class AIService:
    """Orchestrator service for all AI operations on capsules."""

    def __init__(self):
        self.transcription_service = TranscriptionService()
        self.summary_generator = SummaryGenerator()
        self.sentiment_detector = SentimentDetector()
        self.vision_analyzer = VisionAnalyzer()
        self.recap_generator = RecapGenerator()

    def analyze_capsule(self, capsule_id: int, db: Session) -> Optional[AIAnalysis]:
        """
        Full analysis pipeline with error isolation.

        Creates AIAnalysis record upfront (pending), updates incrementally,
        marks completed when done. Each step is wrapped in try/except so
        individual failures don't block the rest of the pipeline.

        Pipeline order:
        1. Transcribe audio/video media
        2. Detect sentiment on text_content
        3. Analyze images
        4. Generate text summary
        5. Generate recap

        Args:
            capsule_id: ID of the capsule to analyze
            db: Database session

        Returns:
            AIAnalysis object if successful, None if capsule not found or catastrophic error
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

            # Create AIAnalysis record upfront with pending status
            ai_analysis = AIAnalysis(
                capsule_id=capsule_id,
                processing_status="pending",
            )
            db.add(ai_analysis)
            db.commit()
            db.refresh(ai_analysis)

            # Transition to processing
            ai_analysis.processing_status = "processing"
            db.commit()

            now = datetime.now(timezone.utc)
            media_urls = capsule.media_urls if capsule.media_urls else []

            # ----------------------------------------------------------
            # Step 1: Transcribe audio/video media
            # ----------------------------------------------------------
            transcriptions: List[str] = list(capsule.transcriptions) if capsule.transcriptions else []
            video_summaries: List[dict] = []

            try:
                audio_video_urls = [
                    url for url in media_urls
                    if self._get_media_type(url) in ("audio", "video")
                ]

                if audio_video_urls and len(transcriptions) < len(audio_video_urls):
                    for media_url in audio_video_urls:
                        media_type = self._get_media_type(media_url)
                        transcription = self.transcription_service.transcribe_media(
                            media_url=media_url,
                            media_type=media_type,
                        )
                        t_text = transcription if transcription else ""

                        if transcription:
                            transcriptions.append(transcription)

                        # For video files, also generate a per-video summary
                        if media_type == "video":
                            vid_summary_text = None
                            try:
                                if t_text:
                                    vid_summary_text = self.summary_generator.generate_summary(
                                        text_content=t_text,
                                        transcriptions=[],
                                        created_at=capsule.created_at,
                                        unlocked_at=now,
                                    )
                            except Exception as ve:
                                logger.error(f"Video summary generation failed for {media_url}: {ve}")

                            video_summaries.append({
                                "media_url": media_url,
                                "transcription": t_text,
                                "summary": vid_summary_text or "",
                            })

                    # Persist transcriptions on the capsule
                    if transcriptions:
                        capsule.transcriptions = transcriptions
                        db.commit()

                # Save partial results
                ai_analysis.video_summaries = video_summaries if video_summaries else None
                db.commit()

            except Exception as e:
                logger.error(f"Transcription step failed for capsule {capsule_id}: {e}")

            # ----------------------------------------------------------
            # Step 2: Detect sentiment on text_content
            # ----------------------------------------------------------
            sentiment: Optional[dict] = None

            try:
                text_for_sentiment = capsule.text_content
                if text_for_sentiment and text_for_sentiment.strip():
                    sentiment = self.sentiment_detector.detect_sentiment(text_for_sentiment)
                    if sentiment:
                        ai_analysis.sentiment_label = sentiment.get("label")
                        ai_analysis.sentiment_confidence = sentiment.get("confidence")
                        ai_analysis.tone_description = sentiment.get("tone_description")
                        db.commit()
            except Exception as e:
                logger.error(f"Sentiment detection step failed for capsule {capsule_id}: {e}")

            # ----------------------------------------------------------
            # Step 3: Analyze images
            # ----------------------------------------------------------
            image_analyses: Optional[List[dict]] = None

            try:
                image_urls = [
                    url for url in media_urls
                    if self._get_media_type(url) == "image"
                ]
                if image_urls:
                    image_analyses = self.vision_analyzer.analyze_images(image_urls)
                    ai_analysis.image_analyses = image_analyses if image_analyses else None
                    db.commit()
            except Exception as e:
                logger.error(f"Image analysis step failed for capsule {capsule_id}: {e}")

            # ----------------------------------------------------------
            # Step 4: Generate text summary
            # ----------------------------------------------------------
            summary: Optional[str] = None

            try:
                summary = self.summary_generator.generate_summary(
                    text_content=capsule.text_content or "",
                    transcriptions=transcriptions,
                    created_at=capsule.created_at,
                    unlocked_at=now,
                )
                ai_analysis.summary = summary
                db.commit()
            except Exception as e:
                logger.error(f"Summary generation step failed for capsule {capsule_id}: {e}")

            # ----------------------------------------------------------
            # Step 5: Generate recap
            # ----------------------------------------------------------
            try:
                recap = self.recap_generator.generate_recap(
                    summary=summary,
                    sentiment=sentiment,
                    image_analyses=image_analyses,
                    video_summaries=video_summaries if video_summaries else None,
                    created_at=capsule.created_at,
                    unlocked_at=now,
                )
                ai_analysis.recap_text = recap
                db.commit()
            except Exception as e:
                logger.error(f"Recap generation step failed for capsule {capsule_id}: {e}")

            # ----------------------------------------------------------
            # Mark completed
            # ----------------------------------------------------------
            ai_analysis.processing_status = "completed"
            db.commit()
            db.refresh(ai_analysis)

            logger.info(f"Successfully completed AI analysis for capsule {capsule_id}")
            return ai_analysis

        except Exception as e:
            # Catastrophic error (e.g. DB failure) — mark as failed
            logger.error(f"Catastrophic error during AI analysis for capsule {capsule_id}: {e}")
            try:
                db.rollback()
                # Try to mark the record as failed if it exists
                existing = db.query(AIAnalysis).filter(
                    AIAnalysis.capsule_id == capsule_id
                ).first()
                if existing:
                    existing.processing_status = "failed"
                    existing.error_message = str(e)
                    db.commit()
            except Exception as inner:
                logger.error(f"Failed to update AIAnalysis status to failed: {inner}")
                db.rollback()
            return None

    def _get_media_type(self, media_url: str) -> str:
        """
        Determines media type from URL extension.

        Args:
            media_url: URL of the media file

        Returns:
            'audio', 'video', 'image', or 'unknown'
        """
        url_lower = media_url.lower()

        # Audio formats
        if any(url_lower.endswith(ext) for ext in [".mp3", ".wav", ".m4a"]):
            return "audio"

        # Video formats
        if any(url_lower.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".webm"]):
            return "video"

        # Image formats
        if any(url_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            return "image"

        return "unknown"
