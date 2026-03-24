"""
Tests for the Redis caching module.

Validates: Requirements 14.6 - Caching for frequently accessed data
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.cache import (
    _default_serializer,
    cache_delete,
    cache_delete_pattern,
    cache_get,
    cache_set,
    invalidate_capsule_caches,
    invalidate_public_feed,
    invalidate_user_capsules,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Provide a mock Redis client and patch get_redis_client."""
    client = MagicMock()
    with patch("app.cache.get_redis_client", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

class TestDefaultSerializer:
    def test_serializes_datetime(self):
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = _default_serializer(dt)
        assert result == "2025-01-15T12:00:00+00:00"

    def test_raises_for_unsupported_type(self):
        with pytest.raises(TypeError):
            _default_serializer(set())


# ---------------------------------------------------------------------------
# cache_get
# ---------------------------------------------------------------------------

class TestCacheGet:
    def test_returns_deserialized_value(self, mock_redis):
        mock_redis.get.return_value = json.dumps({"capsules": [], "total": 0})
        result = cache_get("public_feed")
        assert result == {"capsules": [], "total": 0}
        mock_redis.get.assert_called_once_with("public_feed")

    def test_returns_none_on_miss(self, mock_redis):
        mock_redis.get.return_value = None
        assert cache_get("missing_key") is None

    def test_returns_none_on_error(self, mock_redis):
        mock_redis.get.side_effect = Exception("connection lost")
        assert cache_get("key") is None


# ---------------------------------------------------------------------------
# cache_set
# ---------------------------------------------------------------------------

class TestCacheSet:
    def test_sets_value_with_ttl(self, mock_redis):
        data = {"capsules": [{"id": 1}], "total": 1}
        result = cache_set("public_feed", data, ttl=60)
        assert result is True
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "public_feed"
        assert args[1] == 60
        assert json.loads(args[2]) == data

    def test_serializes_datetime_values(self, mock_redis):
        dt = datetime(2025, 6, 1, tzinfo=timezone.utc)
        data = {"unlock_date": dt}
        result = cache_set("key", data, ttl=30)
        assert result is True
        stored = json.loads(mock_redis.setex.call_args[0][2])
        assert stored["unlock_date"] == "2025-06-01T00:00:00+00:00"

    def test_returns_false_on_error(self, mock_redis):
        mock_redis.setex.side_effect = Exception("connection lost")
        assert cache_set("key", "val") is False


# ---------------------------------------------------------------------------
# cache_delete / cache_delete_pattern
# ---------------------------------------------------------------------------

class TestCacheDelete:
    def test_deletes_key(self, mock_redis):
        assert cache_delete("public_feed") is True
        mock_redis.delete.assert_called_once_with("public_feed")

    def test_returns_false_on_error(self, mock_redis):
        mock_redis.delete.side_effect = Exception("err")
        assert cache_delete("key") is False


class TestCacheDeletePattern:
    def test_deletes_matching_keys(self, mock_redis):
        mock_redis.scan_iter.return_value = ["user_capsules:1", "user_capsules:2"]
        assert cache_delete_pattern("user_capsules:*") is True
        mock_redis.delete.assert_called_once_with("user_capsules:1", "user_capsules:2")

    def test_no_op_when_no_keys_match(self, mock_redis):
        mock_redis.scan_iter.return_value = []
        assert cache_delete_pattern("nonexistent:*") is True
        mock_redis.delete.assert_not_called()

    def test_returns_false_on_error(self, mock_redis):
        mock_redis.scan_iter.side_effect = Exception("err")
        assert cache_delete_pattern("*") is False


# ---------------------------------------------------------------------------
# Convenience invalidation helpers
# ---------------------------------------------------------------------------

class TestInvalidationHelpers:
    def test_invalidate_public_feed(self, mock_redis):
        invalidate_public_feed()
        mock_redis.delete.assert_called_once_with("public_feed")

    def test_invalidate_user_capsules(self, mock_redis):
        invalidate_user_capsules(42)
        mock_redis.delete.assert_called_once_with("user_capsules:42")

    def test_invalidate_capsule_caches(self, mock_redis):
        invalidate_capsule_caches(7)
        calls = [str(c) for c in mock_redis.delete.call_args_list]
        assert any("user_capsules:7" in c for c in calls)
        assert any("public_feed" in c for c in calls)
