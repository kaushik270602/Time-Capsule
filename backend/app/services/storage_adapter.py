import boto3
from botocore.exceptions import ClientError
from app.config import settings
import uuid
import time
from typing import Optional


class UploadFailedError(Exception):
    """Raised when file upload fails"""
    pass


class StorageAdapter:
    """Abstraction layer for S3/Cloudinary storage"""
    
    def __init__(self):
        self.s3_client = None
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
    
    def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        content_type: str,
        max_retries: int = 3
    ) -> str:
        """
        Upload file to storage with retry logic.
        
        Args:
            file_content: File content as bytes
            file_name: Original file name
            content_type: MIME type
            max_retries: Maximum retry attempts
            
        Returns:
            File URL
            
        Raises:
            UploadFailedError: If upload fails after retries
        """
        if not self.s3_client or not settings.S3_BUCKET_NAME:
            raise UploadFailedError("S3 not configured")
        
        # Generate unique file key
        file_extension = file_name.split('.')[-1] if '.' in file_name else ''
        file_key = f"{uuid.uuid4()}.{file_extension}" if file_extension else str(uuid.uuid4())
        
        # Retry logic
        for attempt in range(max_retries):
            try:
                self.s3_client.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=file_key,
                    Body=file_content,
                    ContentType=content_type
                )
                
                # Generate URL
                url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{file_key}"
                return url
                
            except ClientError as e:
                if attempt == max_retries - 1:
                    raise UploadFailedError(f"Upload failed after {max_retries} attempts: {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        raise UploadFailedError("Upload failed")
    
    def generate_signed_url(
        self,
        file_key: str,
        expiration_seconds: int = 3600
    ) -> str:
        """
        Generate time-limited signed URL.
        
        Args:
            file_key: S3 object key
            expiration_seconds: URL expiration time
            
        Returns:
            Signed URL
        """
        if not self.s3_client or not settings.S3_BUCKET_NAME:
            return file_key  # Return original key if S3 not configured
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.S3_BUCKET_NAME,
                    'Key': file_key
                },
                ExpiresIn=expiration_seconds
            )
            return url
        except ClientError:
            return file_key
    
    def delete_file(self, file_key: str) -> bool:
        """
        Remove media file from storage.
        
        Args:
            file_key: S3 object key
            
        Returns:
            True if successful
        """
        if not self.s3_client or not settings.S3_BUCKET_NAME:
            return False
        
        try:
            self.s3_client.delete_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=file_key
            )
            return True
        except ClientError:
            return False
