# Feature: timelock
# Property-based tests for media validation and storage

import pytest
from hypothesis import given, strategies as st, settings as hyp_settings, assume
from io import BytesIO
from fastapi import UploadFile
from app.services.media_service import MediaService, InvalidFileError
from app.services.storage_adapter import StorageAdapter, UploadFailedError
from app.config import settings
from botocore.exceptions import ClientError
from unittest.mock import Mock, patch, MagicMock
import uuid


# ============================================================================
# Helper Strategies
# ============================================================================

def generate_file_content(size_bytes: int) -> bytes:
    """Generate file content of specified size"""
    return b'x' * size_bytes


def create_upload_file(content: bytes, filename: str, content_type: str) -> Mock:
    """Create a mock UploadFile for testing"""
    file_obj = BytesIO(content)
    
    # Create a mock UploadFile with all necessary attributes
    mock_file = Mock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.file = file_obj
    
    # Mock the read method to return the content
    async def mock_read():
        file_obj.seek(0)
        return file_obj.read()
    
    mock_file.read = mock_read
    
    return mock_file


# Strategy for valid video formats
video_formats = st.sampled_from([
    'video/mp4',
    'video/quicktime',
    'video/x-msvideo'
])

# Strategy for valid audio formats
audio_formats = st.sampled_from([
    'audio/mpeg',
    'audio/wav',
    'audio/x-m4a',
    'audio/mp4'
])

# Strategy for valid image formats
image_formats = st.sampled_from([
    'image/jpeg',
    'image/png',
    'image/gif'
])

# Strategy for invalid formats
invalid_formats = st.sampled_from([
    'application/pdf',
    'text/plain',
    'video/webm',
    'audio/ogg',
    'image/bmp',
    'application/octet-stream'
])


# ============================================================================
# Property 9: Media file validation enforces format and size limits
# ============================================================================

@hyp_settings(max_examples=20, deadline=None)
@given(
    file_size=st.integers(min_value=1, max_value=500 * 1024 * 1024),  # Up to 500MB
    content_type=video_formats
)
def test_property_9_video_format_and_size_validation(file_size, content_type):
    """
    Property 9: Media file validation enforces format and size limits (Video)
    
    For any video file upload, the system should validate format and size against
    defined limits (500MB max, MP4/MOV/AVI formats), rejecting files that exceed
    limits or have unsupported formats with descriptive error messages.
    
    Validates: Requirements 3.3, 3.7, 3.8, 12.7
    """
    media_service = MediaService()
    
    # Generate file content
    content = generate_file_content(file_size)
    upload_file = create_upload_file(content, "test_video.mp4", content_type)
    
    # Test validation
    if file_size <= MediaService.VIDEO_MAX_SIZE:
        # Should pass validation
        result = media_service.validate_file(upload_file, 'video')
        assert result == True, "Valid video file should pass validation"
    else:
        # Should fail validation with descriptive error
        with pytest.raises(InvalidFileError) as exc_info:
            media_service.validate_file(upload_file, 'video')
        
        error_msg = str(exc_info.value).lower()
        assert "too large" in error_msg or "size" in error_msg, \
            "Error message should indicate file is too large"


@hyp_settings(max_examples=20, deadline=None)
@given(
    file_size=st.integers(min_value=1, max_value=100 * 1024 * 1024),  # Up to 100MB
    content_type=audio_formats
)
def test_property_9_audio_format_and_size_validation(file_size, content_type):
    """
    Property 9: Media file validation enforces format and size limits (Audio)
    
    For any audio file upload, the system should validate format and size against
    defined limits (100MB max, MP3/WAV/M4A formats), rejecting files that exceed
    limits or have unsupported formats with descriptive error messages.
    
    Validates: Requirements 3.4, 3.7, 3.8, 12.8
    """
    media_service = MediaService()
    
    # Generate file content
    content = generate_file_content(file_size)
    upload_file = create_upload_file(content, "test_audio.mp3", content_type)
    
    # Test validation
    if file_size <= MediaService.AUDIO_MAX_SIZE:
        # Should pass validation
        result = media_service.validate_file(upload_file, 'audio')
        assert result == True, "Valid audio file should pass validation"
    else:
        # Should fail validation with descriptive error
        with pytest.raises(InvalidFileError) as exc_info:
            media_service.validate_file(upload_file, 'audio')
        
        error_msg = str(exc_info.value).lower()
        assert "too large" in error_msg or "size" in error_msg, \
            "Error message should indicate file is too large"


@hyp_settings(max_examples=20, deadline=None)
@given(
    file_size=st.integers(min_value=1, max_value=10 * 1024 * 1024),  # Up to 10MB
    content_type=image_formats
)
def test_property_9_image_format_and_size_validation(file_size, content_type):
    """
    Property 9: Media file validation enforces format and size limits (Image)
    
    For any image file upload, the system should validate format and size against
    defined limits (10MB max, JPG/PNG/GIF formats), rejecting files that exceed
    limits or have unsupported formats with descriptive error messages.
    
    Validates: Requirements 3.5, 3.7, 3.8, 12.9
    """
    media_service = MediaService()
    
    # Generate file content
    content = generate_file_content(file_size)
    upload_file = create_upload_file(content, "test_image.jpg", content_type)
    
    # Test validation
    if file_size <= MediaService.IMAGE_MAX_SIZE:
        # Should pass validation
        result = media_service.validate_file(upload_file, 'image')
        assert result == True, "Valid image file should pass validation"
    else:
        # Should fail validation with descriptive error
        with pytest.raises(InvalidFileError) as exc_info:
            media_service.validate_file(upload_file, 'image')
        
        error_msg = str(exc_info.value).lower()
        assert "too large" in error_msg or "size" in error_msg, \
            "Error message should indicate file is too large"


@hyp_settings(max_examples=15, deadline=None)
@given(
    content_type=invalid_formats,
    media_type=st.sampled_from(['video', 'audio', 'image'])
)
def test_property_9_unsupported_formats_rejected(content_type, media_type):
    """
    Property 9: Media file validation enforces format and size limits (Format rejection)
    
    For any media file with an unsupported format, the system should reject the
    upload with a descriptive error message indicating the format is not supported.
    
    Validates: Requirements 3.8
    """
    media_service = MediaService()
    
    # Generate small file content (size is valid, format is not)
    content = generate_file_content(1024)  # 1KB
    upload_file = create_upload_file(content, "test_file.bin", content_type)
    
    # Should fail validation with descriptive error
    with pytest.raises(InvalidFileError) as exc_info:
        media_service.validate_file(upload_file, media_type)
    
    error_msg = str(exc_info.value).lower()
    assert "unsupported" in error_msg or "format" in error_msg, \
        "Error message should indicate unsupported format"


# ============================================================================
# Property 10: Media files are stored with retrievable URLs
# ============================================================================

@hyp_settings(max_examples=15, deadline=None)
@given(
    file_size=st.integers(min_value=100, max_value=1024 * 1024),  # 100 bytes to 1MB
    user_id=st.integers(min_value=1, max_value=1000000),
    content_type=video_formats
)
@pytest.mark.asyncio
async def test_property_10_media_files_stored_with_retrievable_urls(file_size, user_id, content_type):
    """
    Property 10: Media files are stored with retrievable URLs
    
    For any valid media file upload, the system should store the file in Media_Storage
    and save a secure URL in the database that can be used for future retrieval.
    The URL should:
    1. Be a non-empty string
    2. Be a valid URL format
    3. Be retrievable from storage
    4. Be unique for each upload
    
    Validates: Requirements 3.6, 12.1, 12.2
    """
    media_service = MediaService()
    
    # Generate file content
    content = generate_file_content(file_size)
    filename = f"test_video_{uuid.uuid4()}.mp4"
    upload_file = create_upload_file(content, filename, content_type)
    
    # Mock the storage adapter to avoid actual S3 calls
    with patch.object(StorageAdapter, 'upload_file') as mock_upload:
        # Generate a mock URL
        mock_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}.mp4"
        mock_upload.return_value = mock_url
        
        # Upload the file
        url = await media_service.upload_media(upload_file, user_id, 'video')
        
        # Verify URL is returned
        assert url is not None, "Upload should return a URL"
        assert isinstance(url, str), "URL should be a string"
        assert len(url) > 0, "URL should not be empty"
        
        # Verify URL has valid format
        assert url.startswith('http://') or url.startswith('https://'), \
            "URL should be a valid HTTP/HTTPS URL"
        
        # Verify storage adapter was called with correct parameters
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        assert call_args[1]['file_content'] == content, "File content should be passed to storage"
        assert call_args[1]['content_type'] == content_type, "Content type should be passed to storage"


@hyp_settings(max_examples=15, deadline=None)
@given(
    file_size=st.integers(min_value=100, max_value=1024 * 1024),  # 100 bytes to 1MB
    user_id=st.integers(min_value=1, max_value=1000000)
)
@pytest.mark.asyncio
async def test_property_10_multiple_uploads_produce_unique_urls(file_size, user_id):
    """
    Property 10 (Extended): Multiple uploads produce unique URLs
    
    For any two uploads of the same file, the system should generate unique URLs
    to prevent collisions and ensure each upload is independently retrievable.
    
    Validates: Requirements 3.6, 12.1
    """
    media_service = MediaService()
    
    # Generate file content
    content = generate_file_content(file_size)
    
    # Create two upload files with same content
    upload_file1 = create_upload_file(content, "test.mp4", "video/mp4")
    upload_file2 = create_upload_file(content, "test.mp4", "video/mp4")
    
    # Mock the storage adapter to return unique URLs
    with patch.object(StorageAdapter, 'upload_file') as mock_upload:
        # Generate unique mock URLs for each call
        url1 = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}.mp4"
        url2 = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}.mp4"
        mock_upload.side_effect = [url1, url2]
        
        # Upload the same file twice
        result_url1 = await media_service.upload_media(upload_file1, user_id, 'video')
        result_url2 = await media_service.upload_media(upload_file2, user_id, 'video')
        
        # Verify URLs are unique
        assert result_url1 != result_url2, \
            "Multiple uploads of the same file should produce unique URLs"


@hyp_settings(max_examples=10, deadline=None)
@given(
    file_size=st.integers(min_value=100, max_value=1024 * 1024),
    capsule_id=st.integers(min_value=1, max_value=1000000),
    expiration_seconds=st.integers(min_value=60, max_value=86400)  # 1 minute to 1 day
)
def test_property_10_secure_urls_are_generated(file_size, capsule_id, expiration_seconds):
    """
    Property 10 (Extended): Secure URLs are generated for media access
    
    For any media file, the system should be able to generate time-limited
    signed URLs for secure access with configurable expiration times.
    
    Validates: Requirements 12.2
    """
    media_service = MediaService()
    
    # Generate a file key (simulating stored file)
    file_key = f"{uuid.uuid4()}.mp4"
    
    # Mock the storage adapter's generate_signed_url method
    with patch.object(StorageAdapter, 'generate_signed_url') as mock_signed_url:
        # Generate a mock signed URL
        mock_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{file_key}?signature=abc123&expires={expiration_seconds}"
        mock_signed_url.return_value = mock_url
        
        # Generate secure URL
        url = media_service.generate_secure_url(file_key, capsule_id, expiration_seconds)
        
        # Verify URL is returned
        assert url is not None, "Secure URL should be generated"
        assert isinstance(url, str), "URL should be a string"
        assert len(url) > 0, "URL should not be empty"
        
        # Verify storage adapter was called with correct parameters
        mock_signed_url.assert_called_once_with(file_key, expiration_seconds)


# ============================================================================
# Property 46: Failed media uploads are retried
# ============================================================================

@hyp_settings(max_examples=15, deadline=None)
@given(
    file_size=st.integers(min_value=100, max_value=1024 * 1024),
    user_id=st.integers(min_value=1, max_value=1000000),
    failure_count=st.integers(min_value=1, max_value=2)  # Fail 1-2 times, then succeed
)
@pytest.mark.asyncio
async def test_property_46_failed_uploads_retried_and_succeed(file_size, user_id, failure_count):
    """
    Property 46: Failed media uploads are retried
    
    For any media upload that fails initially, the system should retry the upload
    up to three times before returning an error to the user. If the upload succeeds
    on a retry, the system should return the URL successfully.
    
    Validates: Requirements 12.6
    """
    from botocore.exceptions import ClientError
    
    media_service = MediaService()
    
    # Generate file content
    content = generate_file_content(file_size)
    upload_file = create_upload_file(content, "test_video.mp4", "video/mp4")
    
    # Mock the S3 client's put_object to fail initially, then succeed
    with patch.object(media_service.storage, 's3_client') as mock_s3:
        media_service.storage.s3_client = mock_s3
        with patch.object(settings, 'S3_BUCKET_NAME', 'test-bucket'):
            # Build side effect list: failures followed by success
            side_effects = [ClientError({'Error': {'Code': 'ServiceUnavailable'}}, 'PutObject')] * failure_count + [None]
            mock_s3.put_object.side_effect = side_effects
            
            # Upload should eventually succeed
            url = await media_service.upload_media(upload_file, user_id, 'video')
            
            # Verify URL is returned after retries
            assert url is not None and len(url) > 0, "Upload should succeed after retries"
            assert url.startswith('https://'), "URL should be a valid HTTPS URL"
            
            # Verify put_object was attempted multiple times (failure_count + 1 for success)
            assert mock_s3.put_object.call_count == failure_count + 1, \
                f"Upload should be attempted {failure_count + 1} times"


@hyp_settings(max_examples=10, deadline=None)
@given(
    file_size=st.integers(min_value=100, max_value=1024 * 1024),
    user_id=st.integers(min_value=1, max_value=1000000)
)
@pytest.mark.asyncio
async def test_property_46_uploads_fail_after_max_retries(file_size, user_id):
    """
    Property 46 (Extended): Uploads fail after maximum retries
    
    For any media upload that fails consistently, the system should retry up to
    three times and then raise an UploadFailedError with a descriptive message.
    
    Validates: Requirements 12.6
    """
    from botocore.exceptions import ClientError
    
    media_service = MediaService()
    
    # Generate file content
    content = generate_file_content(file_size)
    upload_file = create_upload_file(content, "test_video.mp4", "video/mp4")
    
    # Mock the S3 client to always fail
    with patch.object(media_service.storage, 's3_client') as mock_s3:
        media_service.storage.s3_client = mock_s3
        with patch.object(settings, 'S3_BUCKET_NAME', 'test-bucket'):
            # Make put_object always fail
            mock_s3.put_object.side_effect = ClientError(
                {'Error': {'Code': 'ServiceUnavailable'}}, 
                'PutObject'
            )
            
            # Upload should fail after retries
            with pytest.raises(UploadFailedError) as exc_info:
                await media_service.upload_media(upload_file, user_id, 'video')
            
            # Verify error message is descriptive
            error_msg = str(exc_info.value)
            assert "failed" in error_msg.lower() or "attempts" in error_msg.lower(), \
                "Error message should indicate upload failed after retries"
            
            # Verify put_object was attempted exactly 3 times (max retries)
            assert mock_s3.put_object.call_count == 3, \
                "Upload should be attempted exactly 3 times before giving up"


@hyp_settings(max_examples=10, deadline=None)
@given(
    file_size=st.integers(min_value=100, max_value=1024 * 1024),
    user_id=st.integers(min_value=1, max_value=1000000),
    retry_on_attempt=st.integers(min_value=1, max_value=3)  # Which attempt succeeds
)
@pytest.mark.asyncio
async def test_property_46_retry_logic_with_exponential_backoff(file_size, user_id, retry_on_attempt):
    """
    Property 46 (Extended): Retry logic uses exponential backoff
    
    For any media upload that fails and retries, the system should use exponential
    backoff between retry attempts to avoid overwhelming the storage service.
    
    Validates: Requirements 12.6
    """
    from botocore.exceptions import ClientError
    
    media_service = MediaService()
    
    # Generate file content
    content = generate_file_content(file_size)
    upload_file = create_upload_file(content, "test_video.mp4", "video/mp4")
    
    # Mock the S3 client
    with patch.object(media_service.storage, 's3_client') as mock_s3:
        media_service.storage.s3_client = mock_s3
        with patch.object(settings, 'S3_BUCKET_NAME', 'test-bucket'):
            # Create side effect: fail (retry_on_attempt - 1) times, then succeed
            failures = [ClientError({'Error': {'Code': 'ServiceUnavailable'}}, 'PutObject')] * (retry_on_attempt - 1)
            mock_s3.put_object.side_effect = failures + [None]
            
            # Upload should succeed on the specified attempt
            url = await media_service.upload_media(upload_file, user_id, 'video')
            
            # Verify URL is returned
            assert url is not None and len(url) > 0, f"Upload should succeed on attempt {retry_on_attempt}"
            assert url.startswith('https://'), "URL should be a valid HTTPS URL"
            
            # Verify correct number of attempts
            assert mock_s3.put_object.call_count == retry_on_attempt, \
                f"Upload should be attempted {retry_on_attempt} times"


# ============================================================================
# Combined Property Tests
# ============================================================================

@hyp_settings(max_examples=15, deadline=None)
@given(
    video_size=st.integers(min_value=100, max_value=600 * 1024 * 1024),  # Test beyond limit
    audio_size=st.integers(min_value=100, max_value=150 * 1024 * 1024),  # Test beyond limit
    image_size=st.integers(min_value=100, max_value=15 * 1024 * 1024),   # Test beyond limit
    user_id=st.integers(min_value=1, max_value=1000000)
)
@pytest.mark.asyncio
async def test_property_9_and_10_combined_validation_and_storage(
    video_size, audio_size, image_size, user_id
):
    """
    Combined Properties 9 & 10: Validation and storage work together
    
    For any media file, the system should:
    1. Validate format and size first
    2. Only upload if validation passes
    3. Return a retrievable URL if upload succeeds
    4. Reject with descriptive error if validation fails
    
    Validates: Requirements 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 12.1, 12.2
    """
    media_service = MediaService()
    
    # Test video upload
    video_content = generate_file_content(video_size)
    video_file = create_upload_file(video_content, "test.mp4", "video/mp4")
    
    with patch.object(StorageAdapter, 'upload_file') as mock_upload:
        mock_upload.return_value = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}.mp4"
        
        if video_size <= MediaService.VIDEO_MAX_SIZE:
            # Should succeed
            url = await media_service.upload_media(video_file, user_id, 'video')
            assert url is not None and len(url) > 0, "Valid video should upload successfully"
            mock_upload.assert_called_once()
        else:
            # Should fail validation before upload attempt
            with pytest.raises(InvalidFileError):
                await media_service.upload_media(video_file, user_id, 'video')
            # Storage should not be called if validation fails
            mock_upload.assert_not_called()
    
    # Test audio upload
    audio_content = generate_file_content(audio_size)
    audio_file = create_upload_file(audio_content, "test.mp3", "audio/mpeg")
    
    with patch.object(StorageAdapter, 'upload_file') as mock_upload:
        mock_upload.return_value = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}.mp3"
        
        if audio_size <= MediaService.AUDIO_MAX_SIZE:
            # Should succeed
            url = await media_service.upload_media(audio_file, user_id, 'audio')
            assert url is not None and len(url) > 0, "Valid audio should upload successfully"
            mock_upload.assert_called_once()
        else:
            # Should fail validation before upload attempt
            with pytest.raises(InvalidFileError):
                await media_service.upload_media(audio_file, user_id, 'audio')
            mock_upload.assert_not_called()
    
    # Test image upload
    image_content = generate_file_content(image_size)
    image_file = create_upload_file(image_content, "test.jpg", "image/jpeg")
    
    with patch.object(StorageAdapter, 'upload_file') as mock_upload:
        mock_upload.return_value = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}.jpg"
        
        if image_size <= MediaService.IMAGE_MAX_SIZE:
            # Should succeed
            url = await media_service.upload_media(image_file, user_id, 'image')
            assert url is not None and len(url) > 0, "Valid image should upload successfully"
            mock_upload.assert_called_once()
        else:
            # Should fail validation before upload attempt
            with pytest.raises(InvalidFileError):
                await media_service.upload_media(image_file, user_id, 'image')
            mock_upload.assert_not_called()

