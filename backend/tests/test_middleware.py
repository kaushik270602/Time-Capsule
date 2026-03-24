"""
Tests for authentication middleware: rate limiting and CSRF protection.

Validates Requirements: 13.8, 15.3, 15.6
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from app.middleware.rate_limiter import (
    RateLimitMiddleware,
    _InMemoryBackend,
    AUTH_MAX_REQUESTS,
    AUTH_PATHS,
    reset_backend,
)
from app.middleware.csrf import (
    CSRFMiddleware,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    EXEMPT_PATHS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(middlewares: list) -> FastAPI:
    """Create a minimal FastAPI app with the given middleware for testing."""
    app = FastAPI()

    for mw in middlewares:
        app.add_middleware(mw)

    @app.get("/")
    async def root():
        return {"ok": True}

    @app.post("/api/auth/login")
    async def login():
        return {"token": "fake"}

    @app.post("/api/capsules")
    async def create_capsule():
        return {"id": 1}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app


# ---------------------------------------------------------------------------
# Rate Limiter Tests
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:

    def setup_method(self):
        reset_backend()

    def test_allows_requests_under_limit(self):
        app = _make_app([RateLimitMiddleware])
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "X-RateLimit-Remaining" in resp.headers

    def test_rate_limits_auth_endpoints(self):
        app = _make_app([RateLimitMiddleware])
        client = TestClient(app)

        for _ in range(AUTH_MAX_REQUESTS):
            resp = client.post("/api/auth/login", json={})
            assert resp.status_code == 200

        # Next request should be rate limited
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert "rate limit" in resp.json()["detail"].lower()

    def test_global_limit_is_generous(self):
        app = _make_app([RateLimitMiddleware])
        client = TestClient(app)

        # Non-auth endpoints should allow many more requests
        for _ in range(50):
            resp = client.get("/")
            assert resp.status_code == 200


class TestInMemoryBackend:

    def test_sliding_window(self):
        backend = _InMemoryBackend()
        key = "test:key"

        for i in range(10):
            limited, remaining = backend.is_rate_limited(key, 10, 60)
            assert not limited

        limited, remaining = backend.is_rate_limited(key, 10, 60)
        assert limited
        assert remaining == 0

    def test_different_keys_independent(self):
        backend = _InMemoryBackend()
        for i in range(5):
            backend.is_rate_limited("key_a", 5, 60)

        limited, _ = backend.is_rate_limited("key_a", 5, 60)
        assert limited

        limited, _ = backend.is_rate_limited("key_b", 5, 60)
        assert not limited


# ---------------------------------------------------------------------------
# CSRF Middleware Tests
# ---------------------------------------------------------------------------

class TestCSRFMiddleware:

    def test_safe_methods_pass_through(self):
        app = _make_app([CSRFMiddleware])
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert CSRF_COOKIE_NAME in resp.cookies

    def test_exempt_paths_pass_through(self):
        app = _make_app([CSRFMiddleware])
        client = TestClient(app)
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 200

    def test_state_changing_request_without_token_rejected(self):
        app = _make_app([CSRFMiddleware])
        client = TestClient(app)
        resp = client.post("/api/capsules", json={})
        assert resp.status_code == 403
        assert "csrf" in resp.json()["detail"].lower()

    def test_state_changing_request_with_valid_token_passes(self):
        app = _make_app([CSRFMiddleware])
        client = TestClient(app)

        # First get a CSRF token via a GET request
        get_resp = client.get("/")
        csrf_token = get_resp.cookies.get(CSRF_COOKIE_NAME)
        assert csrf_token is not None

        # Now POST with the token in both cookie and header
        resp = client.post(
            "/api/capsules",
            json={},
            headers={CSRF_HEADER_NAME: csrf_token},
            cookies={CSRF_COOKIE_NAME: csrf_token},
        )
        assert resp.status_code == 200

    def test_mismatched_tokens_rejected(self):
        app = _make_app([CSRFMiddleware])
        client = TestClient(app)

        resp = client.post(
            "/api/capsules",
            json={},
            headers={CSRF_HEADER_NAME: "wrong-token"},
            cookies={CSRF_COOKIE_NAME: "correct-token"},
        )
        assert resp.status_code == 403
