# Feature: timelock
# Property-based tests for caching

"""
Property 61: Caching improves performance

For any frequently accessed data (public feed, user dashboard), the system
should use caching to reduce database load, with cache invalidation when
underlying data changes.

Validates: Requirements 14.6
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, strategies as st, settings as hyp_settings, assume

from app.cache import (
    cache_delete,
    cache_get,
    cache_set,
    invalidate_capsule_caches,
    invalidate_public_feed,
    invalidate_user_capsules,
)


# ============================================================================
# Helper Strategies
# ============================================================================

# Strategy for cache keys (non-empty ASCII strings without null bytes)
cache_key_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_:-"),
    min_size=1,
    max_size=100,
)

# Strategy for JSON-serializable cache values
json_primitive = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=200),
)

json_value = st.recursive(
    json_primitive,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=5),
    ),
    max_leaves=10,
)

# Strategy for TTL values (positive integers representing seconds)
ttl_strategy = st.integers(min_value=1, max_value=86400)

# Strategy for user IDs
user_id_strategy = st.integers(min_value=1, max_value=1_000_000)


# ============================================================================
# Helpers
# ============================================================================


class FakeRedis:
    """In-memory fake Redis client for property testing.

    Simulates get/setex/delete/scan_iter so we can exercise the real
    cache module logic (serialization, error handling) without a running
    Redis server.
    """

    def __init__(self):
        self._store: dict[str, tuple[str, int | None]] = {}  # key -> (value, ttl)

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            return None
        return entry[0]

    def setex(self, key: str, ttl: int, value: str):
        self._store[key] = (value, ttl)

    def delete(self, *keys: str):
        for k in keys:
            self._store.pop(k, None)

    def scan_iter(self, match: str = "*"):
        import fnmatch
        return [k for k in self._store if fnmatch.fnmatch(k, match)]

    def stored_ttl(self, key: str) -> int | None:
        """Helper – return the TTL that was passed to setex."""
        entry = self._store.get(key)
        return entry[1] if entry else None


def _patch_redis(fake: FakeRedis):
    """Return a context-manager that patches get_redis_client to return *fake*."""
    return patch("app.cache.get_redis_client", return_value=fake)


# ============================================================================
# Property 61: Caching improves performance
# ============================================================================


@hyp_settings(max_examples=50, deadline=None)
@given(key=cache_key_strategy, value=json_value, ttl=ttl_strategy)
def test_property_61_cache_set_then_get_returns_same_data(key, value, ttl):
    """
    Property 61: Caching improves performance – data round-trip

    For any cacheable data, cache_set followed by cache_get must return
    data that is equal to the original value after JSON serialization
    round-trip.

    **Validates: Requirements 14.6**
    """
    fake = FakeRedis()
    with _patch_redis(fake):
        result = cache_set(key, value, ttl=ttl)
        assert result is True, "cache_set should succeed"

        cached = cache_get(key)

        # The cache serializes via JSON, so we compare against the
        # JSON round-tripped version of the original value.
        expected = json.loads(json.dumps(value))
        assert cached == expected, (
            f"cache_get should return the same data that was set. "
            f"Expected {expected!r}, got {cached!r}"
        )


@hyp_settings(max_examples=50, deadline=None)
@given(key=cache_key_strategy, value=json_value, ttl=ttl_strategy)
def test_property_61_cache_invalidation_removes_data(key, value, ttl):
    """
    Property 61: Caching improves performance – invalidation

    For any cached entry, calling cache_delete must remove it so that a
    subsequent cache_get returns None.

    **Validates: Requirements 14.6**
    """
    # None round-trips to JSON null which cache_get returns as None (same as
    # a cache miss), so we skip None values for this invalidation test.
    assume(value is not None)

    fake = FakeRedis()
    with _patch_redis(fake):
        cache_set(key, value, ttl=ttl)

        # Verify data is present
        assert cache_get(key) is not None, "Data should be cached before invalidation"

        # Invalidate
        deleted = cache_delete(key)
        assert deleted is True, "cache_delete should succeed"

        # Verify data is gone
        assert cache_get(key) is None, (
            "cache_get should return None after cache_delete"
        )


@hyp_settings(max_examples=30, deadline=None)
@given(key=cache_key_strategy, value=json_value, ttl=ttl_strategy)
def test_property_61_cache_respects_ttl(key, value, ttl):
    """
    Property 61: Caching improves performance – TTL is stored

    For any cached entry, the TTL passed to cache_set must be forwarded
    to Redis (via setex) so that entries expire automatically.

    **Validates: Requirements 14.6**
    """
    fake = FakeRedis()
    with _patch_redis(fake):
        cache_set(key, value, ttl=ttl)

        stored_ttl = fake.stored_ttl(key)
        assert stored_ttl == ttl, (
            f"TTL stored in Redis should match the requested TTL. "
            f"Expected {ttl}, got {stored_ttl}"
        )


@hyp_settings(max_examples=30, deadline=None)
@given(user_id=user_id_strategy, value=json_value)
def test_property_61_invalidate_user_capsules_clears_cache(user_id, value):
    """
    Property 61: Caching improves performance – user capsule invalidation

    For any user, calling invalidate_user_capsules should remove the
    cached dashboard data for that user so the next request fetches
    fresh data from the database.

    **Validates: Requirements 14.6**
    """
    assume(value is not None)

    fake = FakeRedis()
    with _patch_redis(fake):
        cache_key = f"user_capsules:{user_id}"
        cache_set(cache_key, value, ttl=60)

        # Verify data is present
        assert cache_get(cache_key) is not None

        # Invalidate
        invalidate_user_capsules(user_id)

        # Verify data is gone
        assert cache_get(cache_key) is None, (
            "User capsule cache should be cleared after invalidation"
        )


@hyp_settings(max_examples=30, deadline=None)
@given(value=json_value)
def test_property_61_invalidate_public_feed_clears_cache(value):
    """
    Property 61: Caching improves performance – public feed invalidation

    Calling invalidate_public_feed should remove the cached public feed
    so the next request fetches fresh data from the database.

    **Validates: Requirements 14.6**
    """
    assume(value is not None)

    fake = FakeRedis()
    with _patch_redis(fake):
        cache_set("public_feed", value, ttl=60)

        # Verify data is present
        assert cache_get("public_feed") is not None

        # Invalidate
        invalidate_public_feed()

        # Verify data is gone
        assert cache_get("public_feed") is None, (
            "Public feed cache should be cleared after invalidation"
        )


@hyp_settings(max_examples=30, deadline=None)
@given(user_id=user_id_strategy, user_data=json_value, feed_data=json_value)
def test_property_61_invalidate_capsule_caches_clears_both(user_id, user_data, feed_data):
    """
    Property 61: Caching improves performance – combined invalidation

    For any data change that affects capsules, invalidate_capsule_caches
    should clear both the user's dashboard cache and the public feed cache
    to ensure consistency.

    **Validates: Requirements 14.6**
    """
    assume(user_data is not None)
    assume(feed_data is not None)

    fake = FakeRedis()
    with _patch_redis(fake):
        user_key = f"user_capsules:{user_id}"
        cache_set(user_key, user_data, ttl=60)
        cache_set("public_feed", feed_data, ttl=60)

        # Verify both are present
        assert cache_get(user_key) is not None
        assert cache_get("public_feed") is not None

        # Invalidate both
        invalidate_capsule_caches(user_id)

        # Verify both are gone
        assert cache_get(user_key) is None, (
            "User capsule cache should be cleared"
        )
        assert cache_get("public_feed") is None, (
            "Public feed cache should be cleared"
        )


@hyp_settings(max_examples=30, deadline=None)
@given(key=cache_key_strategy)
def test_property_61_cache_get_returns_none_for_missing_key(key):
    """
    Property 61: Caching improves performance – cache miss

    For any key that has not been set, cache_get should return None
    (a cache miss), allowing the caller to fall back to the database.

    **Validates: Requirements 14.6**
    """
    fake = FakeRedis()
    with _patch_redis(fake):
        result = cache_get(key)
        assert result is None, (
            "cache_get should return None for keys that were never set"
        )
