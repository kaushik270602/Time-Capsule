"""Unit tests for MediaDownloader service."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError

from app.services.media_downloader import MediaDownloader, MediaDownloadError


class TestParseS3Url:
    """Tests for S3 URL parsing."""

    def test_parse_virtual_hosted_style_url(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        result = downloader._parse_s3_url(
            "https://my-bucket.s3.us-east-1.amazonaws.com/path/to/file.mp3"
        )
        assert result == ("my-bucket", "path/to/file.mp3")

    def test_parse_s3_protocol_url(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        result = downloader._parse_s3_url("s3://my-bucket/path/to/file.jpg")
        assert result == ("my-bucket", "path/to/file.jpg")

    def test_parse_non_s3_url_returns_none(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        result = downloader._parse_s3_url("/media/some-file.mp3")
        assert result is None

    def test_parse_s3_url_with_nested_key(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        result = downloader._parse_s3_url(
            "https://bucket.s3.eu-west-1.amazonaws.com/a/b/c/file.png"
        )
        assert result == ("bucket", "a/b/c/file.png")

    def test_parse_s3_protocol_empty_key_returns_none(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        result = downloader._parse_s3_url("s3://bucket/")
        assert result is None


class TestGetExtension:
    """Tests for file extension extraction."""

    def test_mp3_extension(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        assert downloader._get_extension("file.mp3") == ".mp3"

    def test_no_extension(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        assert downloader._get_extension("file") == ""

    def test_nested_path_extension(self):
        downloader = MediaDownloader.__new__(MediaDownloader)
        assert downloader._get_extension("path/to/image.jpg") == ".jpg"


class TestDownloadToTemp:
    """Tests for download_to_temp method."""

    @patch("app.services.media_downloader.StorageAdapter")
    def test_download_from_s3_success(self, MockStorage):
        mock_storage = MockStorage.return_value
        mock_storage.use_s3 = True
        mock_storage.s3_client = MagicMock()

        downloader = MediaDownloader()

        # Mock download_file to write content to the temp file
        def fake_download(bucket, key, path):
            with open(path, "wb") as f:
                f.write(b"fake audio content")

        mock_storage.s3_client.download_file.side_effect = fake_download

        url = "https://my-bucket.s3.us-east-1.amazonaws.com/audio/test.mp3"
        temp_path = downloader.download_to_temp(url)

        try:
            assert os.path.exists(temp_path)
            assert temp_path.endswith(".mp3")
            with open(temp_path, "rb") as f:
                assert f.read() == b"fake audio content"
            mock_storage.s3_client.download_file.assert_called_once_with(
                "my-bucket", "audio/test.mp3", temp_path
            )
        finally:
            downloader.cleanup(temp_path)

    @patch("app.services.media_downloader.StorageAdapter")
    def test_download_from_s3_client_error_raises(self, MockStorage):
        mock_storage = MockStorage.return_value
        mock_storage.use_s3 = True
        mock_storage.s3_client = MagicMock()
        mock_storage.s3_client.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        downloader = MediaDownloader()
        url = "https://my-bucket.s3.us-east-1.amazonaws.com/missing.mp3"

        with pytest.raises(MediaDownloadError, match="S3 download failed"):
            downloader.download_to_temp(url)

    @patch("app.services.media_downloader.StorageAdapter")
    def test_download_from_local_success(self, MockStorage):
        mock_storage = MockStorage.return_value
        mock_storage.use_s3 = False

        # Create a real temp dir to simulate local storage
        with tempfile.TemporaryDirectory() as tmpdir:
            local_dir = Path(tmpdir)
            test_content = b"local file content"
            (local_dir / "test-file.wav").write_bytes(test_content)

            with patch("app.services.media_downloader.LOCAL_MEDIA_DIR", local_dir):
                downloader = MediaDownloader()
                temp_path = downloader.download_to_temp("/media/test-file.wav")

                try:
                    assert os.path.exists(temp_path)
                    assert temp_path.endswith(".wav")
                    with open(temp_path, "rb") as f:
                        assert f.read() == test_content
                finally:
                    downloader.cleanup(temp_path)

    @patch("app.services.media_downloader.StorageAdapter")
    def test_download_local_missing_file_raises(self, MockStorage):
        mock_storage = MockStorage.return_value
        mock_storage.use_s3 = False

        with tempfile.TemporaryDirectory() as tmpdir:
            local_dir = Path(tmpdir)
            with patch("app.services.media_downloader.LOCAL_MEDIA_DIR", local_dir):
                downloader = MediaDownloader()
                with pytest.raises(MediaDownloadError, match="Local media file not found"):
                    downloader.download_to_temp("/media/nonexistent.mp3")


class TestCleanup:
    """Tests for cleanup method."""

    @patch("app.services.media_downloader.StorageAdapter")
    def test_cleanup_deletes_file(self, MockStorage):
        downloader = MediaDownloader()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp")
        tmp_path = tmp.name
        tmp.close()

        assert os.path.exists(tmp_path)
        downloader.cleanup(tmp_path)
        assert not os.path.exists(tmp_path)

    @patch("app.services.media_downloader.StorageAdapter")
    def test_cleanup_nonexistent_file_does_not_raise(self, MockStorage):
        downloader = MediaDownloader()
        # Should not raise
        downloader.cleanup("/tmp/nonexistent_file_12345.tmp")

    @patch("app.services.media_downloader.StorageAdapter")
    def test_cleanup_empty_path_does_not_raise(self, MockStorage):
        downloader = MediaDownloader()
        downloader.cleanup("")
