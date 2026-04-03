import json
import logging
import time
from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_SENTIMENT = {"label": "neutral", "confidence": 0.0, "tone_description": ""}

VALID_LABELS = [
    "joyful", "nostalgic", "hopeful", "reflective",
    "anxious", "sad", "excited", "neutral",
]


class SentimentDetector:
    """Detects sentiment and tone using OpenAI Chat Completions API."""

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured. Sentiment detection will fail.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def detect_sentiment(self, text: str, max_retries: int = 3) -> dict:
        """
        Analyzes text and returns sentiment information.

        Args:
            text: The text content to analyze.
            max_retries: Maximum number of retry attempts (default: 3).

        Returns:
            dict with keys: label (str), confidence (float), tone_description (str).
            On failure returns: {"label": "neutral", "confidence": 0.0, "tone_description": ""}.
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for sentiment detection")
            return dict(DEFAULT_SENTIMENT)

        prompt = (
            "Analyze the sentiment and emotional tone of the following text. "
            "Respond with ONLY a JSON object containing these fields:\n"
            '- "label": one of "joyful", "nostalgic", "hopeful", "reflective", '
            '"anxious", "sad", "excited", "neutral"\n'
            '- "confidence": a float between 0.0 and 1.0 indicating confidence\n'
            '- "tone_description": a one-sentence description of the emotional tone\n\n'
            f"Text:\n{text}"
        )

        for attempt in range(max_retries):
            try:
                logger.info(f"Detecting sentiment (attempt {attempt + 1}/{max_retries})")

                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a sentiment analysis assistant. "
                                "Always respond with valid JSON only, no extra text."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=200,
                    temperature=0.3,
                )

                raw = response.choices[0].message.content.strip()
                result = json.loads(raw)
                return self._validate_result(result)

            except (APIError, RateLimitError, APIConnectionError) as e:
                logger.error(
                    f"OpenAI API error during sentiment detection (attempt {attempt + 1}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(
                        f"Sentiment detection failed after {max_retries} attempts"
                    )
                    return dict(DEFAULT_SENTIMENT)

            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                logger.error(f"Failed to parse sentiment response: {e}")
                return dict(DEFAULT_SENTIMENT)

            except Exception as e:
                logger.error(
                    f"Unexpected error during sentiment detection (attempt {attempt + 1}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(
                        f"Sentiment detection failed after {max_retries} attempts due to unexpected error"
                    )
                    return dict(DEFAULT_SENTIMENT)

        return dict(DEFAULT_SENTIMENT)

    def _validate_result(self, result: dict) -> dict:
        """Validates and normalises the parsed sentiment result."""
        label = result.get("label", "neutral")
        if label not in VALID_LABELS:
            logger.warning(f"Invalid sentiment label '{label}', defaulting to 'neutral'")
            label = "neutral"

        try:
            confidence = float(result.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        tone_description = str(result.get("tone_description", ""))

        return {
            "label": label,
            "confidence": confidence,
            "tone_description": tone_description,
        }
