import base64
import json
import logging
import time
from typing import Optional, List
from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from app.config import settings
from app.services.media_downloader import MediaDownloader, MediaDownloadError

logger = logging.getLogger(__name__)


class VisionAnalyzer:
    """Analyzes images using OpenAI GPT-4o Vision API."""

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured. Vision analysis will fail.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.downloader = MediaDownloader()

    def analyze_image(self, media_url: str, max_retries: int = 3) -> Optional[dict]:
        """
        Downloads image, encodes as base64, sends to GPT-4o for analysis.

        Args:
            media_url: URL of the image file.
            max_retries: Maximum retry attempts (default: 3).

        Returns:
            {"media_url": str, "caption": str, "tags": List[str]} or None on failure.
        """
        temp_path = None
        try:
            temp_path = self.downloader.download_to_temp(media_url)

            with open(temp_path, "rb") as f:
                image_bytes = f.read()

            b64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Determine mime type from extension
            mime = "image/jpeg"
            lower = media_url.lower()
            if lower.endswith(".png"):
                mime = "image/png"
            elif lower.endswith(".gif"):
                mime = "image/gif"
            elif lower.endswith(".webp"):
                mime = "image/webp"

            for attempt in range(max_retries):
                try:
                    logger.info(f"Analyzing image {media_url} (attempt {attempt + 1}/{max_retries})")

                    response = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are an image analysis assistant for a time capsule app. "
                                    "Always respond with valid JSON only, no extra text."
                                ),
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": (
                                            "Analyze this image and respond with ONLY a JSON object:\n"
                                            '- "caption": a descriptive caption (1-2 sentences)\n'
                                            '- "tags": a list of up to 10 descriptive tags'
                                        ),
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime};base64,{b64_image}"
                                        },
                                    },
                                ],
                            },
                        ],
                        max_tokens=300,
                        temperature=0.3,
                    )

                    raw = response.choices[0].message.content.strip()
                    result = json.loads(raw)
                    return self._validate_result(result, media_url)

                except (APIError, RateLimitError, APIConnectionError) as e:
                    logger.error(f"OpenAI API error during image analysis (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                    else:
                        logger.error(f"Image analysis failed after {max_retries} attempts for {media_url}")
                        return None

                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    logger.error(f"Failed to parse image analysis response: {e}")
                    return None

                except Exception as e:
                    logger.error(f"Unexpected error during image analysis (attempt {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                    else:
                        return None

            return None

        except MediaDownloadError as e:
            logger.error(f"Failed to download image {media_url}: {e}")
            return None

        finally:
            if temp_path:
                self.downloader.cleanup(temp_path)

    def analyze_images(self, media_urls: List[str]) -> List[dict]:
        """
        Analyzes multiple images. Skips failures, returns partial results.

        Args:
            media_urls: List of image URLs to analyze.

        Returns:
            List of successful analysis results.
        """
        results = []
        for url in media_urls:
            try:
                result = self.analyze_image(url)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Unexpected error analyzing image {url}: {e}")
        return results

    def _validate_result(self, result: dict, media_url: str) -> dict:
        """Validates and normalizes the parsed image analysis result."""
        caption = str(result.get("caption", ""))
        tags = result.get("tags", [])

        if not isinstance(tags, list):
            tags = []

        # Ensure tags are strings and limit to 10
        tags = [str(t) for t in tags[:10]]

        return {
            "media_url": media_url,
            "caption": caption,
            "tags": tags,
        }
