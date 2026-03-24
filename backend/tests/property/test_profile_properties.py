# Feature: timelock
# Property-based tests for profile operations — Property 7: Sensitive operations require re-authentication

import pytest
from hypothesis import given, strategies as st, settings
from fastapi.testclient import TestClient

from app.models.base import Base
from app.models.user import User
from app.utils.password import PasswordHasher
from app.utils.jwt import JWTManager
from app.database import get_db
from app.main import app
from app.middleware.rate_limiter import reset_backend

# Re-use the shared test engine from tests/conftest.py
from tests.conftest import engine, TestingSessionLocal, override_get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
# setup_shared_db, client, and db_session are inherited from tests/conftest.py


def _create_verified_user(db, email="user@example.com", password="Password1"):
    """Helper to create a verified user directly in the DB."""
    hasher = PasswordHasher()
    user = User(
        email=email,
        password_hash=hasher.hash_password(password),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_csrf_headers(client, auth_token=None):
    """Make a GET request to obtain a CSRF cookie, return headers dict."""
    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    resp = client.get("/health", headers=headers)
    csrf_token = resp.cookies.get("csrf_token")
    result = {"X-CSRF-Token": csrf_token}
    if auth_token:
        result["Authorization"] = f"Bearer {auth_token}"
    # Carry cookies forward by using the same client (TestClient keeps a session)
    return result, {"csrf_token": csrf_token}


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

def valid_email_strategy():
    """Generate emails that pass pydantic EmailStr validation."""
    return st.builds(
        lambda local, domain, tld: f"{local}@{domain}.{tld}",
        local=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
            min_size=1,
            max_size=15,
        ).filter(lambda x: x[0].isalnum()),
        domain=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
            min_size=1,
            max_size=10,
        ).filter(lambda x: x[0].isalnum() and x[-1].isalnum()),
        tld=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz",
            min_size=2,
            max_size=6,
        ),
    )


def valid_password_strategy():
    """Generate passwords within bcrypt's 72-byte limit."""
    return st.text(min_size=8, max_size=50).filter(
        lambda p: len(p.encode("utf-8")) <= 72
    )


# ---------------------------------------------------------------------------
# Property 7: Sensitive operations require re-authentication
# ---------------------------------------------------------------------------


@settings(max_examples=10, deadline=None)
@given(
    new_email=valid_email_strategy(),
    password=valid_password_strategy(),
)
def test_property_7_email_change_requires_correct_password(new_email, password):
    """
    Property 7: Sensitive operations require re-authentication

    For any attempt to change email, the system should require the user's
    current password. Providing the correct password allows the change;
    providing an incorrect password is rejected with 401.

    Validates: Requirements 2.4
    """
    # Fresh DB per example
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_backend()

    db = TestingSessionLocal()
    try:
        user = _create_verified_user(db, email="original@example.com", password=password)
        token = JWTManager.create_token(user.id)
    finally:
        db.close()

    client = TestClient(app)
    headers, cookies = _get_csrf_headers(client, auth_token=token)

    # Correct password → should succeed
    resp = client.put(
        "/api/profile/email",
        json={"new_email": new_email, "current_password": password},
        headers=headers,
        cookies=cookies,
    )
    assert resp.status_code == 200, (
        f"Email change with correct password should succeed, got {resp.status_code}: {resp.text}"
    )


@settings(max_examples=10, deadline=None)
@given(
    password=valid_password_strategy(),
    wrong_password=valid_password_strategy(),
)
def test_property_7_email_change_rejected_with_wrong_password(password, wrong_password):
    """
    Property 7 (Extended): Wrong password is rejected for email change

    For any attempt to change email with an incorrect password, the system
    should reject the request with a 401 Unauthorized status.

    Validates: Requirements 2.4
    """
    if password == wrong_password:
        return

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_backend()

    db = TestingSessionLocal()
    try:
        user = _create_verified_user(db, email="owner@example.com", password=password)
        token = JWTManager.create_token(user.id)
    finally:
        db.close()

    client = TestClient(app)
    headers, cookies = _get_csrf_headers(client, auth_token=token)

    resp = client.put(
        "/api/profile/email",
        json={"new_email": "changed@example.com", "current_password": wrong_password},
        headers=headers,
        cookies=cookies,
    )
    assert resp.status_code == 401, (
        f"Email change with wrong password should be rejected, got {resp.status_code}: {resp.text}"
    )


def test_property_7_email_change_without_auth_rejected():
    """
    Property 7 (Extended): Unauthenticated email change is rejected

    Attempting to change email without a valid JWT should be rejected.

    Validates: Requirements 2.4
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_backend()

    client = TestClient(app)
    # Get CSRF token first
    headers, cookies = _get_csrf_headers(client)

    resp = client.put(
        "/api/profile/email",
        json={"new_email": "hacker@example.com", "current_password": "anything"},
        headers=headers,
        cookies=cookies,
    )
    # Without Bearer token the auth dependency rejects before CSRF even matters,
    # but the CSRF middleware runs first so we may get 401 or 403.
    assert resp.status_code in (401, 403), (
        f"Email change without auth should be rejected, got {resp.status_code}"
    )


def test_property_7_email_change_with_expired_token_rejected():
    """
    Property 7 (Extended): Expired token is rejected for sensitive operations

    An attempt to change email with an expired JWT should require
    re-authentication by rejecting the request.

    Validates: Requirements 2.4, 15.5
    """
    import time

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_backend()

    db = TestingSessionLocal()
    try:
        user = _create_verified_user(db, email="expiry@example.com", password="Password1")
        # Create a token that expires immediately
        token = JWTManager.create_token(user.id, expiration_hours=0)
    finally:
        db.close()

    time.sleep(1)

    client = TestClient(app)
    headers, cookies = _get_csrf_headers(client, auth_token=token)

    resp = client.put(
        "/api/profile/email",
        json={"new_email": "new@example.com", "current_password": "Password1"},
        headers=headers,
        cookies=cookies,
    )
    assert resp.status_code == 401, (
        f"Email change with expired token should be rejected, got {resp.status_code}"
    )
