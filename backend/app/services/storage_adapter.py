import os
import logging
import uuid
import time
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)

# Local storage directory (inside the container)
LOCAL_MEDIA_DIR = Path("/app/media_uploads")


class UploadFailedError(Exception):
    """Raised when file upload fails"""
    pass


class StorageAdapter:
    """Abstraction layer for S3 with local filesystem fallback."""

    def __init__(self):
        self.use_s3 = bool(
            settings.AWS_ACCESS_KEY_ID
            and settings.AWS_SECRET_ACCESS_KEY
            and settings.S3_BUCKET_NAME
        )
        self.s3_client = None
        if self.use_s3:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
                config=boto3.session.Config(s3={"addressing_style": "virtual"}, signature_version="s3v4"),
                endpoint_url=f"https://s3.{settings.AWS_REGION}.amazonaws.com",
            )
        else:
            # Ensure local media directory exists
            try:
                LOCAL_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            except OSError:
                logger.warning("Cannot create %s — local uploads may fail", LOCAL_MEDIA_DIR)
            logger.info("S3 not configured — using local filesystem storage at %s", LOCAL_MEDIA_DIR)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str,
        max_retries: int = 3,
    ) -> str:
        file_extension = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
        file_key = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())

        if self.use_s3:
            return self._upload_s3(file_content, file_key, content_type, max_retries)
        return self._upload_local(file_content, file_key)

    def _upload_s3(self, file_content: bytes, file_key: str, content_type: str, max_retries: int) -> str:
        for attempt in range(max_retries):
            try:
                self.s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=file_key,
                    Body=file_content,
                    ContentType=content_type,
                )
                return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{file_key}"
            except ClientError as e:
                if attempt == max_retries - 1:
                    raise UploadFailedError(f"Upload failed after {max_retries} attempts: {e}")
                time.sleep(2 ** attempt)
        raise UploadFailedError("Upload failed")

    def _upload_local(self, file_content: bytes, file_key: str) -> str:
        dest = LOCAL_MEDIA_DIR / file_key
        try:
            dest.write_bytes(file_content)
        except OSError as e:
            raise UploadFailedError(f"Local upload failed: {e}")
        # Return a URL path served by FastAPI's static mount
        return f"/media/{file_key}"

    # ------------------------------------------------------------------
    # Signed / public URL
    # ------------------------------------------------------------------

    def generate_signed_url(self, file_key: str, expiration_seconds: int = 3600) -> str:
        if not self.use_s3:
            return file_key  # local paths are already usable
        try:
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": file_key},
                ExpiresIn=expiration_seconds,
            )
        except ClientError:
            return file_key

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_file(self, file_key: str) -> bool:
        if not self.use_s3:
            path = LOCAL_MEDIA_DIR / file_key.lstrip("/media/")
            try:
                path.unlink(missing_ok=True)
                return True
            except OSError:
                return False
        try:
            self.s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=file_key)
            return True
        except ClientError:
            return False
