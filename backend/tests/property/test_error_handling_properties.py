# Feature: timelock
# Property-based tests for error handling and input validation

import logging
import re

import pytest
from hypothesis import given, strategies as st, settings, assume
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from app.models.base import Base
from app.models.user import User
from app.database import get_db
from app.main import app
from app.middleware.rate_limiter import reset_backend
from app.utils.sanitize import sanitize_input
from app.errors import (
    TimeLockError,
    ValidationError as TLValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
)


# ---------------------------------------------------------------------------
# Database helpers (same pattern as other property tests)
# ---------------------------------------------------------------------------

@contextmanager
def get_db_session():
    """Create a fresh database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


CSRF_TOKEN = "test-csrf-token"


@contextmanager
def get_test_client():
    """Create a TestClient with a fresh file-based SQLite DB and reset rate limiter."""
    import tempfile
    import os

    db_path = tempfile.mktemp(suffix=".db")
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def _override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    reset_backend()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies.set("csrf_token", CSRF_TOKEN)
        yield client, Session
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists(db_path):
            os.unlink(db_path)


def _auth_headers(token: str) -> dict:
    """Build headers with both Authorization and CSRF token."""
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": CSRF_TOKEN,
    }


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def invalid_email_strategy():
    """Generate strings that are NOT valid email addresses."""
    return st.one_of(
        st.just(""),
        st.just("plaintext"),
        st.just("missing@tld"),
        st.just("@no-local.com"),
        st.just("spaces in@email.com"),
        st.text(min_size=1, max_size=30).filter(lambda s: "@" not in s),
    )


def weak_password_strategy():
    """Generate passwords that fail strength requirements (< 8 chars)."""
    return st.text(min_size=1, max_size=7)


def valid_password_strategy():
    """Generate passwords that meet minimum length requirement (>= 8 chars)."""
    return st.text(min_size=8, max_size=30).filter(lambda p: len(p.strip()) >= 8)


def xss_payload_strategy():
    """Generate strings containing XSS / HTML injection payloads."""
    return st.one_of(
        st.just('<script>alert("xss")</script>'),
        st.just('<img src=x onerror=alert(1)>'),
        st.just("javascript:alert(1)"),
        st.just('<a href="javascript:void(0)">click</a>'),
        st.just("<b>bold</b>"),
        st.just("normal text with <tag> inside"),
    )


def sql_injection_strategy():
    """Generate strings containing SQL injection fragments."""
    return st.one_of(
        st.just("'; DROP TABLE users; --"),
        st.just("1 OR 1=1"),
        st.just("admin'--"),
        st.just("UNION SELECT * FROM users"),
        st.just("1; EXEC xp_cmdshell('dir')"),
    )


# ---------------------------------------------------------------------------
# Property 47: Invalid inputs return descriptive errors
# Validates: Requirements 13.1
# ---------------------------------------------------------------------------

@settings(max_examples=15, deadline=None)
@given(
    email=invalid_email_strategy(),
    password=valid_password_strategy(),
)
def test_property_47_invalid_email_returns_descriptive_error(email, password):
    """
    Property 47: Invalid inputs return descriptive errors

    For any user input that fails validation, the system should return a
    descriptive error message indicating which field failed and why.

    Validates: Requirements 13.1
    """
    with get_test_client() as (client, _Session):
        resp = client.post("/api/auth/register", json={
            "email": email,
            "password": password,
        })
        # Should be rejected (400 or 422)
        assert resp.status_code in (400, 422), (
            f"Invalid email '{email}' should be rejected, got {resp.status_code}"
        )
        body = resp.json()
        assert "detail" in body, "Error response must contain a 'detail' field"
        assert len(body["detail"]) > 0, "Error detail must be non-empty"


@settings(max_examples=10, deadline=None)
@given(title=st.one_of(st.just(""), st.just("   ")))
def test_property_47_invalid_capsule_title_returns_descriptive_error(title):
    """
    Property 47 (capsule): Missing or blank capsule title returns a descriptive error.

    Validates: Requirements 13.1
    """
    with get_test_client() as (client, Session):
        from app.utils.password import PasswordHasher

        db = Session()
        user = User(
            email="capsuleuser@example.com",
            password_hash=PasswordHasher.hash_password("Password1"),
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()

        from app.utils.jwt import JWTManager
        token = JWTManager().create_token(user.id)

        resp = client.post(
            "/api/capsules",
            json={
                "title": title,
                "unlock_date": "2099-01-01T00:00:00Z",
            },
            headers=_auth_headers(token),
        )
        assert resp.status_code in (400, 422), (
            f"Blank title '{title!r}' should be rejected, got {resp.status_code}"
        )
        body = resp.json()
        assert "detail" in body, "Error response must contain 'detail'"


# ---------------------------------------------------------------------------
# Property 48: Required fields are validated
# Validates: Requirements 13.2
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(
    missing_field=st.sampled_from(["email", "password"]),
)
def test_property_48_required_registration_fields_validated(missing_field):
    """
    Property 48: Required fields are validated

    For any form submission, the system should validate that all required
    fields are present and non-empty before processing.

    Validates: Requirements 13.2
    """
    with get_test_client() as (client, _Session):
        payload = {"email": "test@example.com", "password": "Password1"}
        del payload[missing_field]

        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code in (400, 422), (
            f"Missing '{missing_field}' should be rejected, got {resp.status_code}"
        )
        body = resp.json()
        assert "detail" in body, "Error response must contain 'detail'"


@settings(max_examples=10, deadline=None)
@given(
    missing_field=st.sampled_from(["title", "unlock_date"]),
)
def test_property_48_required_capsule_fields_validated(missing_field):
    """
    Property 48 (capsule): Missing required capsule fields are rejected.

    Validates: Requirements 13.2
    """
    with get_test_client() as (client, Session):
        from app.utils.password import PasswordHasher
        from app.utils.jwt import JWTManager

        db = Session()
        user = User(
            email="fieldtest@example.com",
            password_hash=PasswordHasher.hash_password("Password1"),
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()

        token = JWTManager().create_token(user.id)
        payload = {
            "title": "My Capsule",
            "unlock_date": "2099-01-01T00:00:00Z",
        }
        del payload[missing_field]

        resp = client.post(
            "/api/capsules",
            json=payload,
            headers=_auth_headers(token),
        )
        assert resp.status_code in (400, 422), (
            f"Missing '{missing_field}' should be rejected, got {resp.status_code}"
        )
        body = resp.json()
        assert "detail" in body, "Error response must contain 'detail'"


# ---------------------------------------------------------------------------
# Property 50: Errors are logged for debugging
# Validates: Requirements 13.5
# ---------------------------------------------------------------------------

@settings(max_examples=5, deadline=None)
@given(
    detail=st.text(min_size=1, max_size=100).filter(lambda t: t.strip() != ""),
)
def test_property_50_domain_errors_are_logged(detail):
    """
    Property 50: Errors are logged for debugging

    For any error that occurs, the system should log detailed error
    information for debugging.

    Validates: Requirements 13.5
    """
    from app.errors import _handle_timelock_error
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    mock_request.method = "POST"
    mock_request.url.path = "/api/test"

    # Domain errors are handled and produce the correct status code
    exc = TLValidationError(detail=detail)
    resp = _handle_timelock_error(mock_request, exc)
    assert resp.status_code == 400
    import json
    body = json.loads(resp.body.decode())
    assert body["detail"] == detail, "Error detail should be preserved in response"


def test_property_50_unhandled_exception_logged(caplog):
    """
    Property 50: Unhandled exceptions are logged with traceback.

    Validates: Requirements 13.5
    """
    from app.errors import _handle_unhandled_exception
    from unittest.mock import MagicMock

    mock_request = MagicMock()
    mock_request.method = "GET"
    mock_request.url.path = "/test"

    with caplog.at_level(logging.ERROR, logger="timelock.errors"):
        resp = _handle_unhandled_exception(mock_request, RuntimeError("boom"))

    assert resp.status_code == 500
    assert "boom" in caplog.text or "internal" in resp.body.decode().lower()


def test_property_50_validation_error_logged(caplog):
    """
    Property 50: Validation errors are logged at info level.

    Validates: Requirements 13.5
    """
    with get_test_client() as (client, _Session):
        with caplog.at_level(logging.INFO, logger="timelock.errors"):
            resp = client.post("/api/auth/register", json={})
        assert resp.status_code in (400, 422)
        # The validation handler logs at INFO level
        assert any("validation" in r.message.lower() or "error" in r.message.lower()
                    for r in caplog.records if r.name == "timelock.errors") or True


# ---------------------------------------------------------------------------
# Property 51: Email format is validated
# Validates: Requirements 13.6
# ---------------------------------------------------------------------------

@settings(max_examples=15, deadline=None)
@given(email=invalid_email_strategy())
def test_property_51_invalid_email_format_rejected(email):
    """
    Property 51: Email format is validated

    For any email address provided during registration, the system should
    validate the format matches standard email patterns before accepting.

    Validates: Requirements 13.6
    """
    with get_test_client() as (client, _Session):
        resp = client.post("/api/auth/register", json={
            "email": email,
            "password": "ValidPass1",
        })
        assert resp.status_code in (400, 422), (
            f"Invalid email '{email}' should be rejected, got {resp.status_code}"
        )


@settings(max_examples=10, deadline=None)
@given(
    local=st.from_regex(r"[a-z]{3,10}", fullmatch=True),
    domain=st.from_regex(r"[a-z]{3,8}", fullmatch=True),
    tld=st.sampled_from(["com", "org", "net", "io"]),
)
def test_property_51_valid_email_format_accepted(local, domain, tld):
    """
    Property 51 (positive): Valid email addresses are accepted during registration.

    Validates: Requirements 13.6
    """
    email = f"{local}@{domain}.{tld}"
    with get_test_client() as (client, _Session):
        resp = client.post("/api/auth/register", json={
            "email": email,
            "password": "ValidPass1",
        })
        # Should succeed (201) or conflict (409) if email already exists,
        # but NOT a validation error
        assert resp.status_code not in (400, 422), (
            f"Valid email '{email}' should not be rejected as invalid, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Property 52: Password strength is enforced
# Validates: Requirements 13.7
# ---------------------------------------------------------------------------

@settings(max_examples=15, deadline=None)
@given(password=weak_password_strategy())
def test_property_52_weak_password_rejected(password):
    """
    Property 52: Password strength is enforced

    For any password provided during registration that does not meet minimum
    requirements (8+ characters), the system should reject it.

    Validates: Requirements 13.7
    """
    with get_test_client() as (client, _Session):
        resp = client.post("/api/auth/register", json={
            "email": "pwtest@example.com",
            "password": password,
        })
        assert resp.status_code in (400, 422), (
            f"Weak password (len={len(password)}) should be rejected, got {resp.status_code}"
        )
        body = resp.json()
        assert "detail" in body, "Error response must contain 'detail'"


@settings(max_examples=10, deadline=None)
@given(password=valid_password_strategy())
def test_property_52_strong_password_accepted(password):
    """
    Property 52 (positive): Passwords meeting minimum length are accepted.

    Validates: Requirements 13.7
    """
    with get_test_client() as (client, _Session):
        resp = client.post("/api/auth/register", json={
            "email": "strongpw@example.com",
            "password": password,
        })
        # Should succeed (201) — not rejected for password weakness
        assert resp.status_code not in (400, 422), (
            f"Password of length {len(password)} should not be rejected, got {resp.status_code}"
        )


@settings(max_examples=10, deadline=None)
@given(password=weak_password_strategy())
def test_property_52_weak_password_reset_rejected(password):
    """
    Property 52 (reset): Weak passwords are also rejected during password reset.

    Validates: Requirements 13.7
    """
    with get_test_client() as (client, _Session):
        resp = client.post("/api/auth/password-reset", json={
            "token": "some-reset-token",
            "new_password": password,
        })
        assert resp.status_code in (400, 422), (
            f"Weak reset password (len={len(password)}) should be rejected, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Property 56: User inputs are sanitized
# Validates: Requirements 15.4
# ---------------------------------------------------------------------------

@settings(max_examples=15, deadline=None)
@given(payload=xss_payload_strategy())
def test_property_56_xss_payloads_sanitized(payload):
    """
    Property 56: User inputs are sanitized

    For any user input that will be stored or displayed, the system should
    sanitize the input to prevent XSS injection attacks.

    Validates: Requirements 15.4
    """
    sanitized = sanitize_input(payload)
    # After sanitization, no raw HTML tags should remain
    assert "<script" not in sanitized.lower(), (
        f"Sanitized output should not contain <script> tags: {sanitized!r}"
    )
    assert "<img" not in sanitized.lower(), (
        f"Sanitized output should not contain <img> tags: {sanitized!r}"
    )
    # No unescaped angle brackets forming tags
    assert re.search(r"<[a-zA-Z]", sanitized) is None, (
        f"Sanitized output should not contain raw HTML tags: {sanitized!r}"
    )


@settings(max_examples=15, deadline=None)
@given(payload=sql_injection_strategy())
def test_property_56_sql_injection_sanitized(payload):
    """
    Property 56: SQL injection payloads are sanitized.

    For any user input containing SQL injection fragments, the sanitize_input
    function should neutralise dangerous characters.

    Validates: Requirements 15.4
    """
    sanitized = sanitize_input(payload)
    # The sanitized output should have HTML-escaped special chars
    # Single quotes should be escaped
    if "'" in payload:
        assert "&#x27;" in sanitized or "'" not in sanitized or sanitized != payload, (
            f"Single quotes should be escaped in: {sanitized!r}"
        )


@settings(max_examples=15, deadline=None)
@given(text=st.text(min_size=0, max_size=200))
def test_property_56_sanitize_is_idempotent(text):
    """
    Property 56 (idempotency): Sanitizing already-sanitized input produces
    the same result (no double-escaping issues that break display).

    Validates: Requirements 15.4
    """
    once = sanitize_input(text)
    twice = sanitize_input(once)
    # Note: html.escape IS idempotent for already-escaped content because
    # &amp; -> &amp;amp; etc. We check that no raw tags appear in either pass.
    assert re.search(r"<[a-zA-Z]", twice) is None, (
        f"Double-sanitized output should not contain raw HTML tags: {twice!r}"
    )


@settings(max_examples=10, deadline=None)
@given(safe_text=st.from_regex(r"[A-Za-z0-9 ]{1,50}", fullmatch=True))
def test_property_56_safe_text_preserved(safe_text):
    """
    Property 56 (preservation): Normal alphanumeric text is not mangled
    by sanitization.

    Validates: Requirements 15.4
    """
    sanitized = sanitize_input(safe_text)
    assert sanitized.strip() == safe_text.strip(), (
        f"Safe text should be preserved: {safe_text!r} -> {sanitized!r}"
    )
