# Feature: timelock
# Property-based tests for transcription

import pytest
from hypothesis import given, strategies as st, settings as hyp_settings
from unittest.mock import Mock, patch, MagicMock
from app.services.transcription_service import TranscriptionService, TranscriptionFailedError
from app.services.media_downloader import MediaDownloadError
from openai import OpenAIError, APIError, RateLimitError
import uuid
import tempfile
import os


# ============================================================================
# Helper Strategies
# ============================================================================

# Strategy for valid audio formats
audio_extensions = st.sampled_from(['.mp3', '.wav', '.m4a'])

# Strategy for valid video formats
video_extensions = st.sampled_from(['.mp4', '.mov', '.avi'])

# Strategy for media types
media_types = st.sampled_from(['audio', 'video'])

# Strategy for transcription text (simulating Whisper output)
transcription_text = st.text(min_size=10, max_size=500, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po')
))


def _create_temp_file(suffix='.mp3'):
    """Create a real temp file for tests and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.write(b"fake audio data")
    tmp.close()
    return tmp.name


# ============================================================================
# Property 41: Audio and video files are transcribed
# ============================================================================

@hyp_settings(max_examples=20, deadline=None)
@given(
    media_type=st.just('audio'),
    extension=audio_extensions,
    transcription_result=transcription_text
)
def test_property_41_audio_files_are_transcribed(media_type, extension, transcription_result):
    """
    Property 41: Audio and video files are transcribed (Audio)
    
    For any audio file (MP3, WAV, M4A) uploaded to a capsule, the system should
    transcribe the audio content to text using Whisper AI and store the transcription
    linked to the capsule.
    
    Validates: Requirements 11.1, 11.8
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        media_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{extension}"
        
        # Create a real temp file for the mock to return
        temp_path = _create_temp_file(suffix=extension)
        try:
            mock_downloader.download_to_temp.return_value = temp_path
            mock_client.audio.transcriptions.create.return_value = transcription_result
            
            result = transcription_service.transcribe_media(media_url, media_type)
            
            assert result is not None, "Audio transcription should return text"
            assert isinstance(result, str), "Transcription should be a string"
            assert len(result) > 0, "Transcription should not be empty"
            assert result == transcription_result, "Transcription should match Whisper output"
            
            mock_client.audio.transcriptions.create.assert_called_once()
            mock_downloader.download_to_temp.assert_called_once_with(media_url)
            mock_downloader.cleanup.assert_called_once_with(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


@hyp_settings(max_examples=20, deadline=None)
@given(
    media_type=st.just('video'),
    extension=video_extensions,
    transcription_result=transcription_text
)
def test_property_41_video_files_are_transcribed(media_type, extension, transcription_result):
    """
    Property 41: Audio and video files are transcribed (Video)
    
    For any video file (MP4, MOV, AVI) uploaded to a capsule, the system should
    extract the audio track and transcribe it to text using Whisper AI.
    
    Validates: Requirements 11.2, 11.9
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        media_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{extension}"
        
        temp_path = _create_temp_file(suffix=extension)
        try:
            mock_downloader.download_to_temp.return_value = temp_path
            mock_client.audio.transcriptions.create.return_value = transcription_result
            
            result = transcription_service.transcribe_media(media_url, media_type)
            
            assert result is not None, "Video transcription should return text"
            assert isinstance(result, str), "Transcription should be a string"
            assert len(result) > 0, "Transcription should not be empty"
            assert result == transcription_result, "Transcription should match Whisper output"
            
            mock_client.audio.transcriptions.create.assert_called_once()
            mock_downloader.download_to_temp.assert_called_once_with(media_url)
            mock_downloader.cleanup.assert_called_once_with(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


@hyp_settings(max_examples=15, deadline=None)
@given(
    media_type=media_types,
    extension=st.one_of(audio_extensions, video_extensions),
    transcription_result=transcription_text
)
def test_property_41_transcription_stored_and_linked(media_type, extension, transcription_result):
    """
    Property 41 (Extended): Transcriptions are stored and linked to capsules
    
    For any audio or video file transcribed, the system should store the transcription
    text and link it to the capsule for future retrieval and AI analysis.
    
    Validates: Requirements 11.3
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        media_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{extension}"
        
        temp_path = _create_temp_file(suffix=extension)
        try:
            mock_downloader.download_to_temp.return_value = temp_path
            mock_client.audio.transcriptions.create.return_value = transcription_result
            
            result = transcription_service.transcribe_media(media_url, media_type)
            
            assert result is not None, "Transcription should be returned for storage"
            assert isinstance(result, str), "Transcription must be a string for database storage"
            assert len(result) > 0, "Transcription should contain content"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


# ============================================================================
# Property 42: Transcription failures are graceful
# ============================================================================

@hyp_settings(max_examples=15, deadline=None)
@given(
    media_type=media_types,
    extension=st.one_of(audio_extensions, video_extensions),
    error_type=st.sampled_from(['APIError', 'MediaDownloadError', 'UnexpectedError'])
)
def test_property_42_transcription_failures_are_graceful(media_type, extension, error_type):
    """
    Property 42: Transcription failures are graceful
    
    For any transcription operation that fails, the system should log the error
    and return None (allowing the capsule to be created/accessed without transcription),
    rather than raising an exception that would block capsule operations.
    
    Validates: Requirements 11.5
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        media_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{extension}"
        
        if error_type == 'MediaDownloadError':
            # Simulate download failure
            mock_downloader.download_to_temp.side_effect = MediaDownloadError("Download failed")
            
            result = transcription_service.transcribe_media(media_url, media_type)
            assert result is None, "Transcription should return None on download failure"
            return
        
        # For API errors, download succeeds but API call fails
        temp_path = _create_temp_file(suffix=extension)
        try:
            mock_downloader.download_to_temp.return_value = temp_path
            
            if error_type == 'APIError':
                mock_request = MagicMock()
                mock_client.audio.transcriptions.create.side_effect = APIError("API Error", request=mock_request, body=None)
            elif error_type == 'UnexpectedError':
                mock_client.audio.transcriptions.create.side_effect = Exception("Unexpected error")
            
            with patch('time.sleep'):
                result = transcription_service.transcribe_media(media_url, media_type)
                
                assert result is None, \
                    f"Transcription should return None on {error_type}, not raise exception"
                mock_downloader.cleanup.assert_called_once_with(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


@hyp_settings(max_examples=10, deadline=None)
@given(
    media_type=media_types,
    extension=st.one_of(audio_extensions, video_extensions),
    failure_count=st.integers(min_value=1, max_value=2)
)
def test_property_42_transcription_retries_on_failure(media_type, extension, failure_count):
    """
    Property 42 (Extended): Transcription failures trigger retries
    
    For any transcription that fails due to transient errors, the system should
    retry the operation with exponential backoff before giving up. If the operation
    succeeds on a retry, the transcription should be returned successfully.
    
    Validates: Requirements 11.5
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        media_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{extension}"
        transcription_result = "This is a test transcription."
        
        temp_path = _create_temp_file(suffix=extension)
        try:
            mock_downloader.download_to_temp.return_value = temp_path
            
            mock_request = MagicMock()
            failures = [APIError("Temporary error", request=mock_request, body=None)] * failure_count
            mock_client.audio.transcriptions.create.side_effect = failures + [transcription_result]
            
            with patch('time.sleep'):
                result = transcription_service.transcribe_media(media_url, media_type)
                
                assert result is not None, "Transcription should succeed after retries"
                assert result == transcription_result, "Transcription should return correct text"
                assert mock_client.audio.transcriptions.create.call_count == failure_count + 1, \
                    f"Transcription should be attempted {failure_count + 1} times"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


@hyp_settings(max_examples=10, deadline=None)
@given(
    media_type=media_types,
    extension=st.one_of(audio_extensions, video_extensions)
)
def test_property_42_transcription_fails_after_max_retries(media_type, extension):
    """
    Property 42 (Extended): Transcription fails gracefully after max retries
    
    For any transcription that fails consistently, the system should retry up to
    three times and then return None (graceful failure) rather than raising an
    exception that would block capsule operations.
    
    Validates: Requirements 11.5
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        media_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{extension}"
        
        temp_path = _create_temp_file(suffix=extension)
        try:
            mock_downloader.download_to_temp.return_value = temp_path
            
            mock_request = MagicMock()
            mock_client.audio.transcriptions.create.side_effect = APIError("Persistent error", request=mock_request, body=None)
            
            with patch('time.sleep'):
                result = transcription_service.transcribe_media(media_url, media_type)
                
                assert result is None, \
                    "Transcription should return None after max retries, not raise exception"
                assert mock_client.audio.transcriptions.create.call_count == 3, \
                    "Transcription should be attempted exactly 3 times before giving up"
                mock_downloader.cleanup.assert_called_once_with(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


@hyp_settings(max_examples=10, deadline=None)
@given(
    invalid_media_type=st.text(min_size=1, max_size=20).filter(
        lambda x: x not in ['audio', 'video']
    ),
    extension=st.one_of(audio_extensions, video_extensions)
)
def test_property_42_invalid_media_type_handled_gracefully(invalid_media_type, extension):
    """
    Property 42 (Extended): Invalid media types are handled gracefully
    
    For any transcription request with an invalid media type, the system should
    return None gracefully rather than raising an exception.
    
    Validates: Requirements 11.5
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        media_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{extension}"
        
        result = transcription_service.transcribe_media(media_url, invalid_media_type)
        
        assert result is None, \
            "Transcription with invalid media type should return None, not raise exception"


# ============================================================================
# Combined Property Tests
# ============================================================================

@hyp_settings(max_examples=15, deadline=None)
@given(
    audio_url=st.builds(
        lambda ext: f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{ext}",
        audio_extensions
    ),
    video_url=st.builds(
        lambda ext: f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{ext}",
        video_extensions
    ),
    audio_transcription=transcription_text,
    video_transcription=transcription_text
)
def test_property_41_multiple_media_files_transcribed(
    audio_url, video_url, audio_transcription, video_transcription
):
    """
    Property 41 (Extended): Multiple media files are transcribed independently
    
    For any capsule with multiple audio and video files, the system should
    transcribe each file independently and store all transcriptions.
    
    Validates: Requirements 11.1, 11.2, 11.3
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        mock_client.audio.transcriptions.create.side_effect = [audio_transcription, video_transcription]
        
        temp_path1 = _create_temp_file(suffix='.mp3')
        temp_path2 = _create_temp_file(suffix='.mp4')
        try:
            mock_downloader.download_to_temp.side_effect = [temp_path1, temp_path2]
            
            audio_result = transcription_service.transcribe_media(audio_url, 'audio')
            video_result = transcription_service.transcribe_media(video_url, 'video')
            
            assert audio_result is not None, "Audio transcription should succeed"
            assert video_result is not None, "Video transcription should succeed"
            assert audio_result == audio_transcription, "Audio transcription should match first result"
            assert video_result == video_transcription, "Video transcription should match second result"
            assert mock_client.audio.transcriptions.create.call_count == 2, "Whisper should be called for each media file"
        finally:
            for p in [temp_path1, temp_path2]:
                if os.path.exists(p):
                    os.unlink(p)


@hyp_settings(max_examples=10, deadline=None)
@given(
    media_type=media_types,
    extension=st.one_of(audio_extensions, video_extensions),
    transcription_result=transcription_text,
    should_fail=st.booleans()
)
def test_property_41_and_42_combined_transcription_with_optional_failure(
    media_type, extension, transcription_result, should_fail
):
    """
    Combined Properties 41 & 42: Transcription succeeds or fails gracefully
    
    For any audio or video file, the system should either:
    1. Successfully transcribe and return text (Property 41)
    2. Fail gracefully and return None without blocking capsule operations (Property 42)
    
    Validates: Requirements 11.1, 11.2, 11.5
    """
    with patch('app.services.transcription_service.OpenAI') as mock_openai_class, \
         patch('app.services.transcription_service.MediaDownloader') as mock_downloader_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_downloader = MagicMock()
        mock_downloader_class.return_value = mock_downloader
        
        transcription_service = TranscriptionService()
        
        media_url = f"https://test-bucket.s3.us-east-1.amazonaws.com/{uuid.uuid4()}{extension}"
        
        temp_path = _create_temp_file(suffix=extension)
        try:
            mock_downloader.download_to_temp.return_value = temp_path
            
            if should_fail:
                mock_request = MagicMock()
                mock_client.audio.transcriptions.create.side_effect = APIError("API Error", request=mock_request, body=None)
            else:
                mock_client.audio.transcriptions.create.return_value = transcription_result
            
            with patch('time.sleep'):
                result = transcription_service.transcribe_media(media_url, media_type)
                
                if should_fail:
                    assert result is None, \
                        "Failed transcription should return None, not raise exception"
                else:
                    assert result is not None, "Successful transcription should return text"
                    assert result == transcription_result, "Transcription should match expected output"
                
                mock_downloader.cleanup.assert_called_once_with(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
