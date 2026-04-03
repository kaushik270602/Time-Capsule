from fastapi import UploadFile
from app.services.storage_adapter import StorageAdapter, UploadFailedError
from typing import Dict


class InvalidFileError(Exception):
    """Raised when file validation fails"""
    pass


class MediaService:
    """Handles media file upload, validation, and retrieval"""
    
    # File size limits in bytes
    VIDEO_MAX_SIZE = 25 * 1024 * 1024   # 25MB (Whisper API limit)
    AUDIO_MAX_SIZE = 25 * 1024 * 1024   # 25MB (Whisper API limit)
    IMAGE_MAX_SIZE = 10 * 1024 * 1024   # 10MB
    
    # Supported formats
    VIDEO_FORMATS = {'video/mp4', 'video/quicktime', 'video/x-msvideo'}
    AUDIO_FORMATS = {'audio/mpeg', 'audio/wav', 'audio/x-m4a', 'audio/mp4'}
    IMAGE_FORMATS = {'image/jpeg', 'image/png', 'image/gif'}
    
    def __init__(self):
        self.storage = StorageAdapter()
    
    def validate_file(self, file: UploadFile, media_type: str) -> bool:
        """
        Check file format and size limits.
        
        Args:
            file: Uploaded file
            media_type: Type of media (video, audio, image)
            
        Returns:
            True if valid
            
        Raises:
            InvalidFileError: If validation fails
        """
        content_type = file.content_type
        
        # Get file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        # Validate based on media type
        if media_type == 'video':
            if content_type not in self.VIDEO_FORMATS:
                raise InvalidFileError(f"Unsupported video format: {content_type}")
            if file_size > self.VIDEO_MAX_SIZE:
                raise InvalidFileError(f"Video file too large ({file_size // (1024*1024)}MB). Max 25MB for AI transcription.")
                
        elif media_type == 'audio':
            if content_type not in self.AUDIO_FORMATS:
                raise InvalidFileError(f"Unsupported audio format: {content_type}")
            if file_size > self.AUDIO_MAX_SIZE:
                raise InvalidFileError(f"Audio file too large ({file_size // (1024*1024)}MB). Max 25MB for AI transcription.")
                
        elif media_type == 'image':
            if content_type not in self.IMAGE_FORMATS:
                raise InvalidFileError(f"Unsupported image format: {content_type}")
            if file_size > self.IMAGE_MAX_SIZE:
                raise InvalidFileError(f"Image file too large: {file_size} bytes (max {self.IMAGE_MAX_SIZE})")
        else:
            raise InvalidFileError(f"Unknown media type: {media_type}")
        
        return True
    
    async def upload_media(
        self,
        file: UploadFile,
        user_id: int,
        media_type: str
    ) -> str:
        """
        Validate file and upload to storage.
        
        Args:
            file: Uploaded file
            user_id: User ID
            media_type: Type of media
            
        Returns:
            Secure URL of uploaded file
            
        Raises:
            InvalidFileError: If validation fails
            UploadFailedError: If upload fails
        """
        # Validate file
        self.validate_file(file, media_type)
        
        # Read file content
        file_content = await file.read()
        
        # Upload to storage
        url = self.storage.upload_file(
            file_content=file_content,
            file_name=file.filename or 'unnamed',
            content_type=file.content_type or 'application/octet-stream'
        )
        
        return url
    
    def generate_secure_url(
        self,
        file_key: str,
        capsule_id: int,
        expiration_seconds: int = 3600
    ) -> str:
        """
        Generate time-limited signed URL with access control.
        
        Args:
            file_key: Storage file key
            capsule_id: Associated capsule ID
            expiration_seconds: URL expiration time
            
        Returns:
            Signed URL
        """
        # TODO: Add capsule access control validation
        return self.storage.generate_signed_url(file_key, expiration_seconds)
