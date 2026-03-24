"""
Rate limiting middleware for FastAPI.

Uses an in-process sliding window counter backed by Redis when available,
falling back to an in-memory dict for development.

Requirements: 13.8, 15.6
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable, Optional

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings


class _InMemoryBackend:
    """Simple in-memory sliding window rate limiter (dev/test fallback)."""

    def __init__(self) -> None:
        # key -> list of timestamps
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """Return (is_limited, remaining) for the given key."""
        now = time.time()
        cutoff = now - window_seconds
        # Prune old entries
        self._hits[key] = [t for t in self._hits[key] if t > cutoff]
        if len(self._hits[key]) >= max_requests:
            return True, 0
        self._hits[key].append(now)
        return False, max_requests - len(self._hits[key])


class _RedisBackend:
    """Redis-backed sliding window rate limiter."""

    def __init__(self, redis_url: str) -> None:
        import redis as _redis

        self._redis = _redis.from_url(redis_url, decode_responses=True)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - window_seconds
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds)
        results = pipe.execute()
        current_count = results[1]
        if current_count >= max_requests:
            # Remove the optimistic add
            self._redis.zrem(key, str(now))
            return True, 0
        remaining = max_requests - (current_count + 1)
        return False, max(remaining, 0)


def _build_backend() -> _InMemoryBackend | _RedisBackend:
    try:
        backend = _RedisBackend(settings.REDIS_URL)
        # Verify the connection actually works (redis client connects lazily)
        backend._redis.ping()
        return backend
    except Exception:
        return _InMemoryBackend()


# Module-level singleton
_backend: Optional[_InMemoryBackend | _RedisBackend] = None


def _get_backend() -> _InMemoryBackend | _RedisBackend:
    global _backend
    if _backend is None:
        _backend = _build_backend()
    return _backend


def reset_backend() -> None:
    """Reset the backend (useful for testing)."""
    global _backend
    _backend = None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

# Default limits
AUTH_MAX_REQUESTS = 20  # per window
AUTH_WINDOW_SECONDS = 60  # 1 minute
GLOBAL_MAX_REQUESTS = 200
GLOBAL_WINDOW_SECONDS = 60

# Paths considered "auth endpoints" that get stricter limits
AUTH_PATHS = frozenset({
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/password-reset-request",
    "/api/auth/password-reset",
})


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limiter(
    max_requests: int = AUTH_MAX_REQUESTS,
    window_seconds: int = AUTH_WINDOW_SECONDS,
    key_prefix: str = "rl",
) -> Callable:
    """Dependency-style rate limiter for individual routes."""

    async def _check(request: Request) -> None:
        backend = _get_backend()
        ip = _client_ip(request)
        key = f"{key_prefix}:{request.url.path}:{ip}"
        limited, _ = backend.is_rate_limited(key, max_requests, window_seconds)
        if limited:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(window_seconds)},
            )

    return _check


# Convenience alias
limiter = rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global rate-limiting middleware.

    Applies stricter limits to auth endpoints and a generous global limit
    to everything else.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        backend = _get_backend()
        ip = _client_ip(request)
        path = request.url.path

        if path in AUTH_PATHS:
            max_req = AUTH_MAX_REQUESTS
            window = AUTH_WINDOW_SECONDS
            key = f"rl:auth:{path}:{ip}"
        else:
            max_req = GLOBAL_MAX_REQUESTS
            window = GLOBAL_WINDOW_SECONDS
            key = f"rl:global:{ip}"

        limited, remaining = backend.is_rate_limited(key, max_req, window)

        if limited:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(window)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
