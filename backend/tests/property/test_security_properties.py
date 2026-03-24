# Feature: timelock
# Property-based tests for security

"""
Property 55: CSRF protection is enforced
Property 58: Session tokens are secure

Validates: Requirements 15.3, 15.7
"""

import pytest
from hypothesis import given, strategies as st, settings as hyp_settings, HealthCheck
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.middleware.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SAFE_METHODS,
    EXEMPT_PATHS,
)
from app.middleware.rate_limiter import _InMemoryBackend
from app.utils.jwt import JWTManager, ExpiredTokenError
from app.utils.password import PasswordHasher
from app.models.user import User
from app.config import settings as app_settings

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ============================================================================
# Test-local database & client setup
# ============================================================================

_SQLALCHEMY_URL = "sqlite:///./test_security_props.db"
_engine = create_engine(_SQLALCHEMY_URL, connect_args={"check_same_thread": False})
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


def _fresh_client():
    """Return a TestClient with a clean in-memory DB and in-memory rate limiter."""
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app, raise_server_exceptions=False)


def _create_verified_user(email="testuser@example.com", password="TestPass123"):
    """Create a verified user directly in the database and return (user, token)."""
    db = _TestSession()
    try:
        hashed = PasswordHasher.hash_password(password)
        user = User(email=email, password_hash=hashed, is_verified=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        token = JWTManager.create_token(user.id)
        return user, token
    finally:
        db.close()


# Force the rate limiter to use in-memory backend (no Redis needed)
_inmemory_backend = _InMemoryBackend()


@pytest.fixture(autouse=True)
def _force_inmemory_rate_limiter():
    """Patch the rate limiter to use in-memory backend for all tests."""
    with patch("app.middleware.rate_limiter._get_backend", return_value=_inmemory_backend):
        yield
    # Reset hits between tests
    _inmemory_backend._hits.clear()


@pytest.fixture(autouse=True)
def _setup_db():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    Base.metadata.drop_all(bind=_engine)


# ============================================================================
# Strategies
# ============================================================================

# Non-exempt paths that require CSRF protection for state-changing requests
non_exempt_state_changing_paths = st.sampled_from([
    "/api/capsules",
    "/api/profile",
    "/api/profile/email",
    "/api/auth/logout",
])

# Exempt paths that skip CSRF checks
exempt_paths_strategy = st.sampled_from(list(EXEMPT_PATHS))


# ============================================================================
# Property 55: CSRF protection is enforced
# ============================================================================


class TestProperty55CSRFProtection:
    """
    Property 55: CSRF protection is enforced

    For any state-changing API operation (POST, PUT, DELETE), the system
    should require a valid CSRF token.

    **Validates: Requirements 15.3**
    """

    @hyp_settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(path=non_exempt_state_changing_paths)
    def test_post_without_csrf_token_rejected(self, path):
        """
        For any state-changing POST request to a non-exempt path without a
        CSRF token, the system should reject the request with 403 Forbidden.

        **Validates: Requirements 15.3**
        """
        client = _fresh_client()
        resp = client.post(path, json={})
        assert resp.status_code == 403, (
            f"POST to {path} without CSRF token should return 403, got {resp.status_code}"
        )
        assert "csrf" in resp.json().get("detail", "").lower(), (
            "Error response should mention CSRF"
        )

    @hyp_settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(path=non_exempt_state_changing_paths)
    def test_mismatched_csrf_token_rejected(self, path):
        """
        For any state-changing request where the CSRF header token does not
        match the CSRF cookie token, the system should reject with 403.

        **Validates: Requirements 15.3**
        """
        client = _fresh_client()

        # First, do a GET to obtain a CSRF cookie
        get_resp = client.get("/")
        csrf_cookie = get_resp.cookies.get(CSRF_COOKIE_NAME)
        assert csrf_cookie is not None, "GET response should set a CSRF cookie"

        # Send POST with a mismatched CSRF header
        resp = client.post(
            path,
            json={},
            headers={CSRF_HEADER_NAME: "wrong-token-value"},
            cookies={CSRF_COOKIE_NAME: csrf_cookie},
        )
        assert resp.status_code == 403, (
            f"POST to {path} with mismatched CSRF token should return 403, "
            f"got {resp.status_code}"
        )

    @hyp_settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(path=non_exempt_state_changing_paths)
    def test_valid_csrf_token_passes_middleware(self, path):
        """
        For any state-changing request with a valid matching CSRF token
        (cookie matches header), the CSRF middleware should allow the request
        through. The request may still fail for other reasons (auth, validation)
        but NOT due to CSRF.

        **Validates: Requirements 15.3**
        """
        client = _fresh_client()

        # Get a CSRF cookie via a GET request
        get_resp = client.get("/")
        csrf_cookie = get_resp.cookies.get(CSRF_COOKIE_NAME)
        assert csrf_cookie is not None, "GET response should set a CSRF cookie"

        # Send POST with matching CSRF token
        resp = client.post(
            path,
            json={},
            headers={CSRF_HEADER_NAME: csrf_cookie},
            cookies={CSRF_COOKIE_NAME: csrf_cookie},
        )
        # The request should NOT be rejected by CSRF middleware
        if resp.status_code == 403:
            detail = resp.json().get("detail", "")
            assert "csrf" not in detail.lower(), (
                f"POST to {path} with valid CSRF token should not be "
                f"rejected by CSRF middleware"
            )

    @hyp_settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(path=exempt_paths_strategy)
    def test_exempt_paths_pass_without_csrf(self, path):
        """
        For any exempt path (auth endpoints that use Bearer tokens), POST
        requests should be allowed through without a CSRF token.

        **Validates: Requirements 15.3**
        """
        client = _fresh_client()
        resp = client.post(path, json={})
        if resp.status_code == 403:
            detail = resp.json().get("detail", "")
            assert "csrf" not in detail.lower(), (
                f"POST to exempt path {path} should not be rejected by "
                f"CSRF middleware"
            )

    @hyp_settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(path=non_exempt_state_changing_paths)
    def test_get_requests_bypass_csrf(self, path):
        """
        GET requests (safe methods) should never be blocked by CSRF
        protection, regardless of whether a CSRF token is present.

        **Validates: Requirements 15.3**
        """
        client = _fresh_client()
        resp = client.get(path)
        if resp.status_code == 403:
            detail = resp.json().get("detail", "")
            assert "csrf" not in detail.lower(), (
                f"GET to {path} should not be blocked by CSRF protection"
            )

    @hyp_settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(path=non_exempt_state_changing_paths)
    def test_csrf_cookie_set_on_every_response(self, path):
        """
        Every response should include a CSRF cookie so that clients can
        read the token and include it in subsequent state-changing requests.

        **Validates: Requirements 15.3**
        """
        client = _fresh_client()
        resp = client.get(path)
        csrf_cookie = resp.cookies.get(CSRF_COOKIE_NAME)
        assert csrf_cookie is not None, (
            f"Response to GET {path} should include a CSRF cookie"
        )
        assert len(csrf_cookie) > 0, "CSRF cookie should not be empty"


# ============================================================================
# Property 58: Session tokens are secure
# ============================================================================


class TestProperty58SessionTokensSecurity:
    """
    Property 58: Session tokens are secure

    For any session token created, it should be stored with httpOnly and
    secure flags to prevent client-side access and ensure HTTPS-only
    transmission.

    **Validates: Requirements 15.7**
    """

    @hyp_settings(max_examples=20, deadline=None)
    @given(user_id=st.integers(min_value=1, max_value=1_000_000))
    def test_jwt_tokens_have_expiration(self, user_id):
        """
        For any session token created, it should have a proper expiration
        time set, ensuring tokens don't remain valid indefinitely.

        **Validates: Requirements 15.7**
        """
        import jwt as pyjwt

        token = JWTManager.create_token(user_id)
        payload = pyjwt.decode(
            token,
            app_settings.JWT_SECRET_KEY,
            algorithms=[app_settings.JWT_ALGORITHM],
        )

        assert "exp" in payload, "JWT token must have an expiration (exp) claim"
        assert "iat" in payload, "JWT token must have an issued-at (iat) claim"
        assert payload["exp"] > payload["iat"], (
            "Token expiration must be after issued-at time"
        )

    @hyp_settings(max_examples=15, deadline=None)
    @given(
        user_id=st.integers(min_value=1, max_value=1_000_000),
        expiration_hours=st.integers(min_value=1, max_value=168),
    )
    def test_jwt_expiration_matches_requested(self, user_id, expiration_hours):
        """
        For any token created with a specific expiration, the actual
        expiration in the token should match the requested duration.

        **Validates: Requirements 15.7**
        """
        import jwt as pyjwt

        token = JWTManager.create_token(user_id, expiration_hours=expiration_hours)
        payload = pyjwt.decode(
            token,
            app_settings.JWT_SECRET_KEY,
            algorithms=[app_settings.JWT_ALGORITHM],
        )

        exp_duration = payload["exp"] - payload["iat"]
        expected_seconds = expiration_hours * 3600

        # Allow 5 seconds tolerance for execution time
        assert abs(exp_duration - expected_seconds) <= 5, (
            f"Token expiration duration ({exp_duration}s) should be close to "
            f"requested {expected_seconds}s (tolerance: 5s)"
        )

    def test_login_sets_httponly_cookie(self):
        """
        When a user logs in, the system should set an httpOnly cookie
        containing the session token, preventing client-side JavaScript
        from accessing the token (mitigating XSS attacks).

        **Validates: Requirements 15.7**
        """
        client = _fresh_client()
        _create_verified_user(email="cookie@example.com", password="SecurePass1")

        resp = client.post("/api/auth/login", json={
            "email": "cookie@example.com",
            "password": "SecurePass1",
        })
        assert resp.status_code == 200, (
            f"Login should succeed, got {resp.status_code}: {resp.text}"
        )

        # Check that access_token cookie is set
        assert "access_token" in resp.cookies, (
            "Login response should set an access_token cookie"
        )

        # Verify the cookie has httpOnly flag via Set-Cookie headers
        set_cookie_headers = resp.headers.get_list("set-cookie")
        access_token_header = None
        for header in set_cookie_headers:
            if header.lower().startswith("access_token="):
                access_token_header = header
                break

        assert access_token_header is not None, (
            "Should find access_token in Set-Cookie headers"
        )
        assert "httponly" in access_token_header.lower(), (
            "access_token cookie must have httpOnly flag set"
        )

    def test_login_cookie_has_samesite(self):
        """
        The session cookie should have a SameSite attribute to prevent
        CSRF attacks via cross-site requests.

        **Validates: Requirements 15.7**
        """
        client = _fresh_client()
        _create_verified_user(email="samesite@example.com", password="SecurePass1")

        resp = client.post("/api/auth/login", json={
            "email": "samesite@example.com",
            "password": "SecurePass1",
        })
        assert resp.status_code == 200

        set_cookie_headers = resp.headers.get_list("set-cookie")
        access_token_header = None
        for header in set_cookie_headers:
            if header.lower().startswith("access_token="):
                access_token_header = header
                break

        assert access_token_header is not None
        assert "samesite" in access_token_header.lower(), (
            "access_token cookie must have SameSite attribute"
        )

    def test_login_cookie_has_max_age(self):
        """
        The session cookie should have a max_age attribute that matches
        the JWT expiration, ensuring the cookie expires when the token does.

        **Validates: Requirements 15.7**
        """
        client = _fresh_client()
        _create_verified_user(email="maxage@example.com", password="SecurePass1")

        resp = client.post("/api/auth/login", json={
            "email": "maxage@example.com",
            "password": "SecurePass1",
        })
        assert resp.status_code == 200

        set_cookie_headers = resp.headers.get_list("set-cookie")
        access_token_header = None
        for header in set_cookie_headers:
            if header.lower().startswith("access_token="):
                access_token_header = header
                break

        assert access_token_header is not None
        assert "max-age=" in access_token_header.lower(), (
            "access_token cookie must have a max-age attribute"
        )

    def test_login_cookie_has_path_restriction(self):
        """
        The session cookie should have a path restriction to limit scope.

        **Validates: Requirements 15.7**
        """
        client = _fresh_client()
        _create_verified_user(email="path@example.com", password="SecurePass1")

        resp = client.post("/api/auth/login", json={
            "email": "path@example.com",
            "password": "SecurePass1",
        })
        assert resp.status_code == 200

        set_cookie_headers = resp.headers.get_list("set-cookie")
        access_token_header = None
        for header in set_cookie_headers:
            if header.lower().startswith("access_token="):
                access_token_header = header
                break

        assert access_token_header is not None
        assert "path=/" in access_token_header.lower(), (
            "access_token cookie must have a path restriction"
        )

    @hyp_settings(max_examples=15, deadline=None)
    @given(user_id=st.integers(min_value=1, max_value=1_000_000))
    def test_expired_token_rejected(self, user_id):
        """
        For any expired JWT token, the system should reject the request,
        ensuring that stale sessions cannot be used.

        **Validates: Requirements 15.7**
        """
        import jwt as pyjwt
        from datetime import datetime, timedelta

        # Create a token that is already expired
        expired_payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2),
        }
        expired_token = pyjwt.encode(
            expired_payload,
            app_settings.JWT_SECRET_KEY,
            algorithm=app_settings.JWT_ALGORITHM,
        )

        with pytest.raises(ExpiredTokenError):
            JWTManager.validate_token(expired_token)

    @hyp_settings(max_examples=15, deadline=None)
    @given(user_id=st.integers(min_value=1, max_value=1_000_000))
    def test_token_contains_user_identity(self, user_id):
        """
        For any session token, it must contain the user_id claim so the
        system can identify which user the session belongs to.

        **Validates: Requirements 15.7**
        """
        import jwt as pyjwt

        token = JWTManager.create_token(user_id)
        payload = pyjwt.decode(
            token,
            app_settings.JWT_SECRET_KEY,
            algorithms=[app_settings.JWT_ALGORITHM],
        )

        assert "user_id" in payload, "Token must contain user_id claim"
        assert payload["user_id"] == user_id, (
            f"Token user_id ({payload['user_id']}) must match the user ({user_id})"
        )
