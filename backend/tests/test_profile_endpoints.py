"""
Unit tests for profile API endpoints.

Validates Requirements: 2.1, 2.2, 2.3, 2.4

Database setup and shared fixtures (client, db_session, setup_shared_db)
are provided by tests/conftest.py.
"""

import pytest

from app.models.user import User
from app.utils.password import PasswordHasher
from app.utils.jwt import JWTManager
from app.main import app

from fastapi.testclient import TestClient

CSRF_TOKEN = "test-csrf-token"


@pytest.fixture
def client():
    """Override the shared client to include CSRF cookie."""
    c = TestClient(app)
    c.cookies.set("csrf_token", CSRF_TOKEN)
    return c


def _create_verified_user(db, email="user@example.com", password="Password1"):
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


def _auth_header(user_id: int) -> dict:
    token = JWTManager.create_token(user_id)
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": CSRF_TOKEN}


# ---------------------------------------------------------------------------
# GET /api/profile (Req 2.1)
# ---------------------------------------------------------------------------

class TestGetProfile:

    def test_get_profile_authenticated(self, client, db_session):
        """Req 2.1: Authenticated user can view their profile."""
        user = _create_verified_user(db_session)
        resp = client.get("/api/profile", headers=_auth_header(user.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@example.com"
        assert data["id"] == user.id
        assert data["is_verified"] is True
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_profile_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        resp = client.get("/api/profile")
        assert resp.status_code in (401, 403)

    def test_get_profile_invalid_token(self, client):
        """Invalid token is rejected."""
        resp = client.get("/api/profile", headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/profile (Req 2.2)
# ---------------------------------------------------------------------------

class TestUpdateProfile:

    def test_update_profile_authenticated(self, client, db_session):
        """Req 2.2: Authenticated user can call update profile."""
        user = _create_verified_user(db_session)
        resp = client.put("/api/profile", json={}, headers=_auth_header(user.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@example.com"

    def test_update_profile_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        resp = client.put("/api/profile", json={})
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PUT /api/profile/email (Req 2.3, 2.4)
# ---------------------------------------------------------------------------

class TestChangeEmail:

    def test_change_email_success(self, client, db_session):
        """Req 2.3/2.4: Email change with correct password succeeds."""
        user = _create_verified_user(db_session)
        resp = client.put("/api/profile/email", json={
            "new_email": "new@example.com",
            "current_password": "Password1",
        }, headers=_auth_header(user.id))
        assert resp.status_code == 200
        assert "verify" in resp.json()["message"].lower()

    def test_change_email_marks_unverified(self, client, db_session):
        """Req 2.3: Email change marks account as unverified."""
        user = _create_verified_user(db_session)
        client.put("/api/profile/email", json={
            "new_email": "new@example.com",
            "current_password": "Password1",
        }, headers=_auth_header(user.id))
        db_session.expire_all()
        updated = db_session.query(User).filter(User.id == user.id).first()
        assert updated.email == "new@example.com"
        assert updated.is_verified is False

    def test_change_email_wrong_password(self, client, db_session):
        """Req 2.4: Wrong current password is rejected."""
        user = _create_verified_user(db_session)
        resp = client.put("/api/profile/email", json={
            "new_email": "new@example.com",
            "current_password": "WrongPassword",
        }, headers=_auth_header(user.id))
        assert resp.status_code == 401
        assert "password" in resp.json()["detail"].lower()

    def test_change_email_duplicate(self, client, db_session):
        """Duplicate email is rejected."""
        _create_verified_user(db_session, email="taken@example.com")
        user = _create_verified_user(db_session, email="me@example.com")
        resp = client.put("/api/profile/email", json={
            "new_email": "taken@example.com",
            "current_password": "Password1",
        }, headers=_auth_header(user.id))
        assert resp.status_code == 409
        assert "already" in resp.json()["detail"].lower()

    def test_change_email_invalid_format(self, client, db_session):
        """Invalid email format is rejected by schema validation."""
        user = _create_verified_user(db_session)
        resp = client.put("/api/profile/email", json={
            "new_email": "not-an-email",
            "current_password": "Password1",
        }, headers=_auth_header(user.id))
        assert resp.status_code == 400

    def test_change_email_unauthenticated(self, client):
        """Unauthenticated request is rejected."""
        resp = client.put("/api/profile/email", json={
            "new_email": "new@example.com",
            "current_password": "Password1",
        })
        assert resp.status_code in (401, 403)

    def test_change_email_same_email(self, client, db_session):
        """Changing to the same email is allowed (no conflict with self)."""
        user = _create_verified_user(db_session)
        resp = client.put("/api/profile/email", json={
            "new_email": "user@example.com",
            "current_password": "Password1",
        }, headers=_auth_header(user.id))
        assert resp.status_code == 200
