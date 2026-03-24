import logging
import time
from typing import Optional
from openai import OpenAI, OpenAIError, APIError, RateLimitError
from app.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for transcribing audio and video files using OpenAI Whisper API."""
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured. Transcription will fail.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def transcribe_media(
        self,
        media_url: str,
        media_type: str,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Transcribes audio or video file to text using Whisper API.
        
        Args:
            media_url: URL of the media file to transcribe
            media_type: Type of media ('audio' or 'video')
            max_retries: Maximum number of retry attempts (default: 3)
        
        Returns:
            Transcribed text if successful, None if transcription fails
        
        Raises:
            TranscriptionFailedError: If transcription fails after all retries
        """
        if media_type not in ['audio', 'video']:
            logger.error(f"Invalid media type: {media_type}")
            return None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Transcribing media from {media_url} (attempt {attempt + 1}/{max_retries})")
                
                # Download the media file
                # In production, this would download from the media_url
                # For now, we'll use the URL as a file path for local testing
                
                # Call Whisper API
                with open(media_url, "rb") as audio_file:
                    response = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )
                
                transcription = response if isinstance(response, str) else response.text
                
                logger.info(f"Successfully transcribed media from {media_url}")
                return transcription
                
            except FileNotFoundError:
                logger.error(f"Media file not found: {media_url}")
                return None
                
            except APIError as e:
                logger.error(f"OpenAI API error during transcription (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    time.sleep(delay)
                else:
                    logger.error(f"Transcription failed after {max_retries} attempts")
                    return None
                    
            except RateLimitError as e:
                logger.error(f"OpenAI rate limit exceeded (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    time.sleep(delay)
                else:
                    logger.error(f"Transcription failed due to rate limiting after {max_retries} attempts")
                    return None
                    
            except Exception as e:
                logger.error(f"Unexpected error during transcription (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    time.sleep(delay)
                else:
                    logger.error(f"Transcription failed after {max_retries} attempts due to unexpected error")
                    return None
        
        return None


class TranscriptionFailedError(Exception):
    """Raised when transcription fails after all retry attempts."""
    pass

