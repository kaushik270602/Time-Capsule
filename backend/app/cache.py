"""
Redis caching utility for TimeLock.

Provides get/set/invalidate methods with JSON serialization and TTL support.
Uses the same Redis instance configured for Celery.

Requirements: 14.6 - Implement caching for frequently accessed data
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level Redis client (lazy-initialized)
_redis_client: Optional[redis.Redis] = None


def _default_serializer(obj: Any) -> str:
    """JSON serializer that handles datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def get_redis_client() -> redis.Redis:
    """Get or create the Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    """
    Get a value from cache.

    Args:
        key: Cache key

    Returns:
        Deserialized value or None if not found / on error
    """
    try:
        client = get_redis_client()
        raw = client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Cache get failed for key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl: int = 60) -> bool:
    """
    Set a value in cache with TTL.

    Args:
        key: Cache key
        value: Value to cache (must be JSON-serializable)
        ttl: Time-to-live in seconds

    Returns:
        True if set successfully, False on error
    """
    try:
        client = get_redis_client()
        serialized = json.dumps(value, default=_default_serializer)
        client.setex(key, ttl, serialized)
        return True
    except Exception as exc:
        logger.warning("Cache set failed for key=%s: %s", key, exc)
        return False


def cache_delete(key: str) -> bool:
    """
    Delete a specific key from cache.

    Args:
        key: Cache key to delete

    Returns:
        True if deleted, False on error
    """
    try:
        client = get_redis_client()
        client.delete(key)
        return True
    except Exception as exc:
        logger.warning("Cache delete failed for key=%s: %s", key, exc)
        return False


def cache_delete_pattern(pattern: str) -> bool:
    """
    Delete all keys matching a pattern.

    Args:
        pattern: Redis glob pattern (e.g. "user_capsules:*")

    Returns:
        True if successful, False on error
    """
    try:
        client = get_redis_client()
        keys = list(client.scan_iter(match=pattern))
        if keys:
            client.delete(*keys)
        return True
    except Exception as exc:
        logger.warning("Cache delete pattern failed for pattern=%s: %s", pattern, exc)
        return False


def invalidate_public_feed() -> None:
    """Invalidate the public feed cache."""
    cache_delete("public_feed")


def invalidate_user_capsules(user_id: int) -> None:
    """Invalidate a user's dashboard capsule cache."""
    cache_delete(f"user_capsules:{user_id}")


def invalidate_capsule_caches(user_id: int) -> None:
    """Invalidate both user capsules and public feed caches (e.g. on create/update/unlock)."""
    invalidate_user_capsules(user_id)
    invalidate_public_feed()
