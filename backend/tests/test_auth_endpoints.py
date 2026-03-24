"""
Unit tests for authentication API endpoints.

Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 1.9, 13.8

Database setup and shared fixtures (client, db_session, setup_shared_db)
are provided by tests/conftest.py.
"""

import time

import pytest

from app.models.user import User
from app.utils.password import PasswordHasher
from app.utils.jwt import JWTManager


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


def _create_unverified_user(db, email="unverified@example.com", password="Password1"):
    """Helper to create an unverified user directly in the DB."""
    hasher = PasswordHasher()
    user = User(
        email=email,
        password_hash=hasher.hash_password(password),
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Registration Tests (Req 1.1, 1.2, 1.4)
# ---------------------------------------------------------------------------

class TestRegister:

    def test_register_valid_user(self, client):
        """Req 1.1: Valid registration creates a new account."""
        resp = client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": "StrongPass1",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["is_verified"] is False
        assert "id" in data
        assert "created_at" in data

    def test_register_duplicate_email(self, client):
        """Req 1.4: Duplicate email registration is rejected."""
        payload = {"email": "dup@example.com", "password": "StrongPass1"}
        resp1 = client.post("/api/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/api/auth/register", json=payload)
        assert resp2.status_code == 409
        assert "already registered" in resp2.json()["detail"].lower()

    def test_register_invalid_email_format(self, client):
        """Req 1.1: Invalid email format is rejected."""
        resp = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "password": "StrongPass1",
        })
        assert resp.status_code == 400

    def test_register_short_password(self, client):
        """Req 1.1: Password below minimum length is rejected."""
        resp = client.post("/api/auth/register", json={
            "email": "short@example.com",
            "password": "Ab1",
        })
        assert resp.status_code == 400

    def test_register_missing_email(self, client):
        """Required fields are validated."""
        resp = client.post("/api/auth/register", json={
            "password": "StrongPass1",
        })
        assert resp.status_code == 400

    def test_register_missing_password(self, client):
        """Required fields are validated."""
        resp = client.post("/api/auth/register", json={
            "email": "nopass@example.com",
        })
        assert resp.status_code == 400

    def test_register_password_is_hashed(self, client, db_session):
        """Req 1.2 / 1.10: Password is stored hashed, not plain text."""
        client.post("/api/auth/register", json={
            "email": "hash@example.com",
            "password": "StrongPass1",
        })
        user = db_session.query(User).filter(User.email == "hash@example.com").first()
        assert user is not None
        assert user.password_hash != "StrongPass1"
        assert user.password_hash.startswith("$2b$")


# ---------------------------------------------------------------------------
# Email Verification Tests (Req 1.3)
# ---------------------------------------------------------------------------

class TestVerifyEmail:

    def test_verify_email_success(self, client):
        """Req 1.3: Valid verification token activates account."""
        resp = client.post("/api/auth/verify-email", json={
            "token": "valid-token",
        })
        assert resp.status_code == 200
        assert "verified" in resp.json()["message"].lower()

    def test_verify_email_missing_token(self, client):
        """Missing token is rejected."""
        resp = client.post("/api/auth/verify-email", json={})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Login Tests (Req 1.5, 1.6)
# ---------------------------------------------------------------------------

class TestLogin:

    def test_login_valid_credentials(self, client, db_session):
        """Req 1.5: Valid credentials return a JWT token."""
        _create_verified_user(db_session)
        resp = client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "Password1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, db_session):
        """Req 1.6: Wrong password is rejected."""
        _create_verified_user(db_session)
        resp = client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "WrongPassword1",
        })
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_login_nonexistent_email(self, client):
        """Req 1.6: Non-existent email is rejected."""
        resp = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "Password1",
        })
        assert resp.status_code == 401

    def test_login_unverified_user(self, client, db_session):
        """Req 1.3/1.5: Unverified user cannot log in."""
        _create_unverified_user(db_session)
        resp = client.post("/api/auth/login", json={
            "email": "unverified@example.com",
            "password": "Password1",
        })
        assert resp.status_code == 403
        assert "not verified" in resp.json()["detail"].lower()

    def test_login_invalid_email_format(self, client):
        """Invalid email format is rejected at schema level."""
        resp = client.post("/api/auth/login", json={
            "email": "bad-email",
            "password": "Password1",
        })
        assert resp.status_code == 400

    def test_login_returns_valid_jwt(self, client, db_session):
        """Req 1.5/1.7: Returned token is a valid JWT."""
        user = _create_verified_user(db_session)
        resp = client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "Password1",
        })
        token = resp.json()["access_token"]
        jwt_mgr = JWTManager()
        user_id = jwt_mgr.validate_token(token)
        assert user_id == user.id


# ---------------------------------------------------------------------------
# Password Reset Tests (Req 1.8, 1.9)
# ---------------------------------------------------------------------------

class TestPasswordReset:

    def test_password_reset_request_existing_email(self, client, db_session):
        """Req 1.8: Reset request for existing email returns success."""
        _create_verified_user(db_session)
        resp = client.post("/api/auth/password-reset-request", json={
            "email": "user@example.com",
        })
        assert resp.status_code == 200
        assert "reset" in resp.json()["message"].lower() or "if" in resp.json()["message"].lower()

    def test_password_reset_request_nonexistent_email(self, client):
        """Req 1.8: Reset request for unknown email still returns success (no info leak)."""
        resp = client.post("/api/auth/password-reset-request", json={
            "email": "ghost@example.com",
        })
        assert resp.status_code == 200

    def test_password_reset_request_invalid_email(self, client):
        """Invalid email format is rejected."""
        resp = client.post("/api/auth/password-reset-request", json={
            "email": "not-valid",
        })
        assert resp.status_code == 400

    def test_password_reset_confirm(self, client):
        """Req 1.9: Password reset with valid token succeeds."""
        resp = client.post("/api/auth/password-reset", json={
            "token": "valid-reset-token",
            "new_password": "NewStrong1",
        })
        assert resp.status_code == 200
        assert "reset" in resp.json()["message"].lower()

    def test_password_reset_confirm_short_password(self, client):
        """Req 1.9: New password must meet minimum length."""
        resp = client.post("/api/auth/password-reset", json={
            "token": "valid-reset-token",
            "new_password": "Ab1",
        })
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Get Current User Tests (Req 1.5, 1.7)
# ---------------------------------------------------------------------------

class TestGetCurrentUser:

    def test_get_me_authenticated(self, client, db_session):
        """Authenticated user can retrieve their profile."""
        user = _create_verified_user(db_session)
        token = JWTManager.create_token(user.id)
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@example.com"
        assert data["id"] == user.id

    def test_get_me_no_token(self, client):
        """Unauthenticated request is rejected."""
        resp = client.get("/api/auth/me")
        assert resp.status_code in (401, 403)

    def test_get_me_invalid_token(self, client):
        """Invalid JWT is rejected."""
        resp = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid.token.here",
        })
        assert resp.status_code == 401

    def test_get_me_expired_token(self, client, db_session):
        """Expired JWT is rejected."""
        user = _create_verified_user(db_session)
        token = JWTManager.create_token(user.id, expiration_hours=0)
        time.sleep(1)
        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rate Limiting Tests (Req 13.8)
# ---------------------------------------------------------------------------

class TestAuthRateLimiting:

    def test_auth_endpoint_rate_limited(self, client):
        """Req 13.8: Auth endpoints are rate limited after threshold."""
        from app.middleware.rate_limiter import AUTH_MAX_REQUESTS

        for _ in range(AUTH_MAX_REQUESTS):
            client.post("/api/auth/login", json={
                "email": "test@example.com",
                "password": "Password1",
            })

        resp = client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "Password1",
        })
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_register_endpoint_rate_limited(self, client):
        """Req 13.8: Register endpoint is also rate limited."""
        from app.middleware.rate_limiter import AUTH_MAX_REQUESTS

        for i in range(AUTH_MAX_REQUESTS):
            client.post("/api/auth/register", json={
                "email": f"user{i}@example.com",
                "password": "StrongPass1",
            })

        resp = client.post("/api/auth/register", json={
            "email": "overflow@example.com",
            "password": "StrongPass1",
        })
        assert resp.status_code == 429

    def test_rate_limit_returns_retry_after(self, client):
        """Req 13.8: Rate limit response includes Retry-After header."""
        from app.middleware.rate_limiter import AUTH_MAX_REQUESTS

        for _ in range(AUTH_MAX_REQUESTS):
            client.post("/api/auth/login", json={
                "email": "t@example.com",
                "password": "x",
            })

        resp = client.post("/api/auth/login", json={
            "email": "t@example.com",
            "password": "x",
        })
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) > 0
