import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from botocore.exceptions import ClientError

from app.services.storage_adapter import StorageAdapter, LOCAL_MEDIA_DIR

logger = logging.getLogger(__name__)


class MediaDownloadError(Exception):
    """Raised when media download from S3 or local storage fails."""
    pass


class MediaDownloader:
    """Downloads media from S3 (or local storage) to temporary files."""

    def __init__(self):
        self.storage = StorageAdapter()

    def _parse_s3_url(self, media_url: str) -> Optional[tuple]:
        """
        Parse an S3 URL to extract bucket and key.

        Supports:
          - https://bucket.s3.region.amazonaws.com/key
          - s3://bucket/key
        Returns (bucket, key) or None if not an S3 URL.
        """
        # s3:// protocol
        if media_url.startswith("s3://"):
            parsed = urlparse(media_url)
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
            if bucket and key:
                return (bucket, key)
            return None

        # https://bucket.s3.region.amazonaws.com/key
        match = re.match(
            r"https?://(.+?)\.s3[.\-]([a-z0-9-]+)\.amazonaws\.com/(.+)",
            media_url,
        )
        if match:
            bucket = match.group(1)
            key = match.group(3)
            return (bucket, key)

        return None

    def _get_extension(self, path_or_key: str) -> str:
        """Extract file extension including the dot, e.g. '.mp3'."""
        _, ext = os.path.splitext(path_or_key)
        return ext

    def download_to_temp(self, media_url: str) -> str:
        """
        Downloads media file to a temporary path.

        For S3 URLs: downloads via boto3.
        For local paths (e.g. /media/file.mp3): reads from local storage dir.

        Returns: path to the temp file.
        Raises: MediaDownloadError on failure.
        """
        try:
            s3_info = self._parse_s3_url(media_url)

            if s3_info and self.storage.use_s3:
                return self._download_from_s3(s3_info[0], s3_info[1])
            else:
                return self._download_from_local(media_url)
        except MediaDownloadError:
            raise
        except Exception as e:
            logger.error(f"Failed to download media from {media_url}: {e}")
            raise MediaDownloadError(f"Failed to download media: {e}") from e

    def _download_from_s3(self, bucket: str, key: str) -> str:
        """Download a file from S3 to a temp file."""
        ext = self._get_extension(key)
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp_path = tmp.name
            tmp.close()

            logger.info(f"Downloading s3://{bucket}/{key} to {tmp_path}")
            self.storage.s3_client.download_file(bucket, key, tmp_path)
            return tmp_path
        except ClientError as e:
            # Clean up partial temp file on failure
            if 'tmp_path' in locals():
                self._safe_delete(tmp_path)
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 download failed for s3://{bucket}/{key}: {error_code} - {e}")
            raise MediaDownloadError(
                f"S3 download failed ({error_code}): {e}"
            ) from e
        except Exception as e:
            if 'tmp_path' in locals():
                self._safe_delete(tmp_path)
            logger.error(f"Unexpected error downloading from S3: {e}")
            raise MediaDownloadError(f"S3 download failed: {e}") from e

    def _download_from_local(self, media_url: str) -> str:
        """Copy a local media file to a temp file."""
        # Strip /media/ prefix to get the file key
        file_key = media_url.lstrip("/")
        if file_key.startswith("media/"):
            file_key = file_key[len("media/"):]

        source_path = LOCAL_MEDIA_DIR / file_key
        if not source_path.exists():
            raise MediaDownloadError(f"Local media file not found: {source_path}")

        ext = self._get_extension(file_key)
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp_path = tmp.name
            tmp.write(source_path.read_bytes())
            tmp.close()
            logger.info(f"Copied local file {source_path} to {tmp_path}")
            return tmp_path
        except Exception as e:
            if 'tmp_path' in locals():
                self._safe_delete(tmp_path)
            logger.error(f"Failed to copy local media file: {e}")
            raise MediaDownloadError(f"Local file copy failed: {e}") from e

    def cleanup(self, temp_path: str) -> None:
        """Deletes temporary file. Logs but doesn't raise on failure."""
        self._safe_delete(temp_path)

    def _safe_delete(self, path: str) -> None:
        """Delete a file, logging but not raising on failure."""
        try:
            if path and os.path.exists(path):
                os.unlink(path)
                logger.debug(f"Cleaned up temp file: {path}")
        except OSError as e:
            logger.warning(f"Failed to clean up temp file {path}: {e}")
