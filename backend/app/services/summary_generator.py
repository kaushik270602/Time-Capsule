import logging
import time
from datetime import datetime
from typing import Optional, List
import openai
from app.config import settings

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """Service for generating AI-powered summaries using OpenAI GPT-4."""
    
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured. Summary generation will fail.")
        openai.api_key = settings.OPENAI_API_KEY
    
    def generate_summary(
        self,
        text_content: str,
        transcriptions: List[str],
        created_at: datetime,
        unlocked_at: datetime,
        max_retries: int = 3
    ) -> Optional[str]:
        """
        Generates contextual summary using GPT-4.
        
        Args:
            text_content: The text content of the capsule
            transcriptions: List of transcribed audio/video content
            created_at: When the capsule was created
            unlocked_at: When the capsule was unlocked
            max_retries: Maximum number of retry attempts (default: 3)
        
        Returns:
            Summary text (max 200 words) if successful, None if generation fails
        """
        # Calculate time elapsed
        time_elapsed = unlocked_at - created_at
        days = time_elapsed.days
        years = days // 365
        remaining_days = days % 365
        
        # Format temporal context
        if years > 0:
            time_ago = f"{years} year{'s' if years > 1 else ''} and {remaining_days} day{'s' if remaining_days != 1 else ''}"
        else:
            time_ago = f"{days} day{'s' if days != 1 else ''}"
        
        # Build the content to summarize
        content_parts = []
        if text_content:
            content_parts.append(f"Text message: {text_content}")
        
        if transcriptions:
            for i, transcription in enumerate(transcriptions, 1):
                content_parts.append(f"Transcription {i}: {transcription}")
        
        if not content_parts:
            logger.warning("No content to summarize")
            return None
        
        full_content = "\n\n".join(content_parts)
        
        # Create the prompt
        prompt = f"""Summarize this time capsule message that was created {time_ago} ago.

The capsule was created on {created_at.strftime('%B %d, %Y')} and just unlocked on {unlocked_at.strftime('%B %d, %Y')}.

Content:
{full_content}

Provide a thoughtful summary that:
1. Captures the key themes and messages
2. Reflects on the temporal context (how much time has passed)
3. Notes any predictions, hopes, or reflections from the past
4. Is concise (maximum 200 words)"""
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Generating summary (attempt {attempt + 1}/{max_retries})")
                
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a thoughtful assistant helping users reflect on their time capsule messages."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.7
                )
                
                summary = response.choices[0].message.content.strip()
                logger.info("Successfully generated summary")
                return summary
                
            except openai.error.APIError as e:
                logger.error(f"OpenAI API error during summary generation (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    time.sleep(delay)
                else:
                    logger.error(f"Summary generation failed after {max_retries} attempts")
                    return None
                    
            except openai.error.RateLimitError as e:
                logger.error(f"OpenAI rate limit exceeded (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    time.sleep(delay)
                else:
                    logger.error(f"Summary generation failed due to rate limiting after {max_retries} attempts")
                    return None
                    
            except Exception as e:
                logger.error(f"Unexpected error during summary generation (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    time.sleep(delay)
                else:
                    logger.error(f"Summary generation failed after {max_retries} attempts due to unexpected error")
                    return None
        
        return None

