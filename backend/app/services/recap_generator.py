import logging
import time
from datetime import datetime
from typing import Optional, List

from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from app.config import settings

logger = logging.getLogger(__name__)


class RecapGenerator:
    """Generates unified memory recap combining all AI insights."""

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured. Recap generation will fail.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_recap(
        self,
        summary: Optional[str],
        sentiment: Optional[dict],
        image_analyses: Optional[List[dict]],
        video_summaries: Optional[List[dict]],
        created_at: datetime,
        unlocked_at: datetime,
        max_retries: int = 3,
    ) -> Optional[str]:
        """
        Generates a 150-300 word narrative-style recap weaving together all
        available AI insights with temporal context.

        Args:
            summary: Text summary of the capsule (may be None).
            sentiment: Dict with label, confidence, tone_description (may be None).
            image_analyses: List of dicts with media_url, caption, tags (may be None).
            video_summaries: List of dicts with media_url, transcription, summary (may be None).
            created_at: When the capsule was created.
            unlocked_at: When the capsule was unlocked.
            max_retries: Maximum retry attempts (default 3).

        Returns:
            Recap text string, or None if no insights are available or generation fails.
        """
        # Return None if ALL insights are None/empty
        has_summary = bool(summary)
        has_sentiment = bool(sentiment)
        has_images = bool(image_analyses)
        has_videos = bool(video_summaries)

        if not any([has_summary, has_sentiment, has_images, has_videos]):
            logger.info("No insights available for recap generation")
            return None

        prompt = self._build_prompt(
            summary, sentiment, image_analyses, video_summaries,
            created_at, unlocked_at,
        )

        for attempt in range(max_retries):
            try:
                logger.info(f"Generating recap (attempt {attempt + 1}/{max_retries})")

                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a warm, reflective storyteller helping someone "
                                "revisit a cherished memory from their past. Write with "
                                "warmth, nostalgia, and personal reflection."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=500,
                    temperature=0.8,
                )

                recap = response.choices[0].message.content.strip()
                logger.info("Successfully generated recap")
                return recap

            except (APIError, RateLimitError, APIConnectionError) as e:
                logger.error(
                    f"OpenAI API error during recap generation (attempt {attempt + 1}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Recap generation failed after {max_retries} attempts")
                    return None

            except Exception as e:
                logger.error(
                    f"Unexpected error during recap generation (attempt {attempt + 1}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(
                        f"Recap generation failed after {max_retries} attempts due to unexpected error"
                    )
                    return None

        return None

    def _build_prompt(
        self,
        summary: Optional[str],
        sentiment: Optional[dict],
        image_analyses: Optional[List[dict]],
        video_summaries: Optional[List[dict]],
        created_at: datetime,
        unlocked_at: datetime,
    ) -> str:
        """Builds the recap prompt from all available insights and temporal context."""
        # Calculate temporal context
        time_elapsed = unlocked_at - created_at
        days = time_elapsed.days
        years = days // 365
        remaining_days = days % 365

        if years > 0:
            time_ago = (
                f"{years} year{'s' if years > 1 else ''} and "
                f"{remaining_days} day{'s' if remaining_days != 1 else ''}"
            )
        else:
            time_ago = f"{days} day{'s' if days != 1 else ''}"

        parts = [
            f"Create a unified memory recap for a time capsule that was sealed "
            f"{time_ago} ago, on {created_at.strftime('%B %d, %Y')}, and just "
            f"opened on {unlocked_at.strftime('%B %d, %Y')}.",
            "",
            "Here are the available insights about this memory:",
        ]

        if summary:
            parts.append(f"\n**Text Summary:**\n{summary}")

        if sentiment:
            label = sentiment.get("label", "")
            confidence = sentiment.get("confidence", 0.0)
            tone = sentiment.get("tone_description", "")
            parts.append(
                f"\n**Emotional Tone:**\n"
                f"Sentiment: {label} (confidence: {confidence:.0%})\n"
                f"Tone: {tone}"
            )

        if image_analyses:
            parts.append("\n**Photos in this memory:**")
            for i, img in enumerate(image_analyses, 1):
                caption = img.get("caption", "")
                tags = img.get("tags", [])
                tag_str = ", ".join(tags) if tags else ""
                parts.append(f"  Photo {i}: {caption}")
                if tag_str:
                    parts.append(f"    Tags: {tag_str}")

        if video_summaries:
            parts.append("\n**Videos in this memory:**")
            for i, vid in enumerate(video_summaries, 1):
                vid_summary = vid.get("summary", "")
                parts.append(f"  Video {i}: {vid_summary}")

        parts.extend([
            "",
            "Write a 150-300 word narrative-style recap that:",
            "1. Weaves together all the insights above into a cohesive reflection",
            "2. References how much time has passed since this memory was created",
            "3. Emphasizes warmth, nostalgia, and personal reflection",
            "4. Speaks directly to the capsule owner in second person",
            "5. Creates a meaningful moment of reconnection with the past",
        ])

        return "\n".join(parts)
