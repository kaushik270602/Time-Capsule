import logging
import time
from typing import Optional
from openai import OpenAI, OpenAIError, APIError, RateLimitError
from app.config import settings
from app.services.media_downloader import MediaDownloader, MediaDownloadError

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for transcribing audio and video files using OpenAI Whisper API."""
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured. Transcription will fail.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.downloader = MediaDownloader()
    
    def transcribe_media(
        self,
        media_url: str,
        media_type: str,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Transcribes audio or video file to text using Whisper API.
        
        Downloads media from S3 via MediaDownloader, transcribes via Whisper,
        and cleans up the temp file afterwards.
        
        Args:
            media_url: URL of the media file to transcribe
            media_type: Type of media ('audio' or 'video')
            max_retries: Maximum number of retry attempts (default: 3)
        
        Returns:
            Transcribed text if successful, None if transcription fails
        """
        if media_type not in ['audio', 'video']:
            logger.error(f"Invalid media type: {media_type}")
            return None
        
        temp_path = None
        try:
            # Download media to a temporary file
            temp_path = self.downloader.download_to_temp(media_url)
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Transcribing media from {media_url} (attempt {attempt + 1}/{max_retries})")
                    
                    with open(temp_path, "rb") as audio_file:
                        response = self.client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            response_format="text"
                        )
                    
                    transcription = response if isinstance(response, str) else response.text
                    
                    logger.info(f"Successfully transcribed media from {media_url}")
                    return transcription
                    
                except APIError as e:
                    logger.error(f"OpenAI API error during transcription (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        delay = 2 ** attempt
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
            
        except MediaDownloadError as e:
            logger.error(f"Failed to download media file: {media_url} - {e}")
            return None
            
        finally:
            if temp_path:
                self.downloader.cleanup(temp_path)


class TranscriptionFailedError(Exception):
    """Raised when transcription fails after all retry attempts."""
    pass
