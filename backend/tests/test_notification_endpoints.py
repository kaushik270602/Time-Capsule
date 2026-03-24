"""
Unit tests for notification API endpoints.

Validates Requirements: 7.2

Database setup and shared fixtures (client, db_session, setup_shared_db)
are provided by tests/conftest.py.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.capsule import Capsule
from app.models.notification import Notification
from app.models.user import User
from app.utils.jwt import JWTManager
from app.utils.password import PasswordHasher

CSRF_TOKEN = "test-csrf-token"


@pytest.fixture
def client():
    """Override the shared client to include CSRF cookie for PUT requests."""
    c = TestClient(app)
    c.cookies.set("csrf_token", CSRF_TOKEN)
    return c


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


def _create_capsule(db, user_id, title="Test Capsule"):
    """Helper to create a capsule for notification foreign key."""
    capsule = Capsule(
        user_id=user_id,
        title=title,
        text_content="Some content",
        unlock_date=datetime.now(timezone.utc) + timedelta(days=30),
        status="locked",
        is_public=False,
    )
    db.add(capsule)
    db.commit()
    db.refresh(capsule)
    return capsule


def _create_notification(db, user_id, capsule_id, message="Your capsule has been unlocked!", is_read=False):
    """Helper to create a notification directly in the DB."""
    notif = Notification(
        user_id=user_id,
        capsule_id=capsule_id,
        message=message,
        is_read=is_read,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def _auth_header(user_id):
    """Helper to build an Authorization header with a valid JWT and CSRF token."""
    token = JWTManager.create_token(user_id)
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": CSRF_TOKEN}


# ---------------------------------------------------------------------------
# GET /api/notifications - Notification Retrieval Tests (Req 7.2)
# ---------------------------------------------------------------------------

class TestGetNotifications:

    def test_get_notifications_returns_user_notifications(self, client, db_session):
        """Req 7.2: Authenticated user can retrieve their notifications."""
        user = _create_verified_user(db_session)
        capsule = _create_capsule(db_session, user.id)
        _create_notification(db_session, user.id, capsule.id, "Capsule unlocked!")

        resp = client.get("/api/notifications", headers=_auth_header(user.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["message"] == "Capsule unlocked!"
        assert data["notifications"][0]["capsule_id"] == capsule.id
        assert data["notifications"][0]["is_read"] is False

    def test_get_notifications_empty(self, client, db_session):
        """Req 7.2: User with no notifications gets an empty list."""
        user = _create_verified_user(db_session)

        resp = client.get("/api/notifications", headers=_auth_header(user.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["notifications"] == []

    def test_get_notifications_multiple(self, client, db_session):
        """Req 7.2: Multiple notifications are returned with correct total."""
        user = _create_verified_user(db_session)
        capsule = _create_capsule(db_session, user.id)
        _create_notification(db_session, user.id, capsule.id, "First notification")
        _create_notification(db_session, user.id, capsule.id, "Second notification")
        _create_notification(db_session, user.id, capsule.id, "Third notification")

        resp = client.get("/api/notifications", headers=_auth_header(user.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["notifications"]) == 3

    def test_get_notifications_only_own(self, client, db_session):
        """Req 7.2: User only sees their own notifications, not other users'."""
        user1 = _create_verified_user(db_session, email="user1@example.com")
        user2 = _create_verified_user(db_session, email="user2@example.com")
        capsule1 = _create_capsule(db_session, user1.id, "Capsule 1")
        capsule2 = _create_capsule(db_session, user2.id, "Capsule 2")
        _create_notification(db_session, user1.id, capsule1.id, "For user1")
        _create_notification(db_session, user2.id, capsule2.id, "For user2")

        resp = client.get("/api/notifications", headers=_auth_header(user1.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["notifications"][0]["message"] == "For user1"

    def test_get_notifications_unauthenticated(self, client):
        """Req 7.2: Unauthenticated request is rejected."""
        resp = client.get("/api/notifications")
        assert resp.status_code in (401, 403)

    def test_get_notifications_invalid_token(self, client):
        """Invalid JWT is rejected."""
        resp = client.get("/api/notifications", headers={
            "Authorization": "Bearer invalid.token.here",
        })
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/notifications/:id/read - Mark Notification as Read (Req 7.2)
# ---------------------------------------------------------------------------

class TestMarkNotificationRead:

    def test_mark_notification_as_read(self, client, db_session):
        """Req 7.2: User can mark their notification as read."""
        user = _create_verified_user(db_session)
        capsule = _create_capsule(db_session, user.id)
        notif = _create_notification(db_session, user.id, capsule.id)

        resp = client.put(f"/api/notifications/{notif.id}/read", headers=_auth_header(user.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_read"] is True
        assert data["id"] == notif.id

    def test_mark_already_read_notification(self, client, db_session):
        """Req 7.2: Marking an already-read notification still succeeds."""
        user = _create_verified_user(db_session)
        capsule = _create_capsule(db_session, user.id)
        notif = _create_notification(db_session, user.id, capsule.id, is_read=True)

        resp = client.put(f"/api/notifications/{notif.id}/read", headers=_auth_header(user.id))
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    def test_mark_nonexistent_notification(self, client, db_session):
        """Req 7.2: Marking a non-existent notification returns 404."""
        user = _create_verified_user(db_session)

        resp = client.put("/api/notifications/99999/read", headers=_auth_header(user.id))
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_mark_other_users_notification(self, client, db_session):
        """Req 7.2: User cannot mark another user's notification as read."""
        user1 = _create_verified_user(db_session, email="owner@example.com")
        user2 = _create_verified_user(db_session, email="other@example.com")
        capsule = _create_capsule(db_session, user1.id)
        notif = _create_notification(db_session, user1.id, capsule.id)

        resp = client.put(f"/api/notifications/{notif.id}/read", headers=_auth_header(user2.id))
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_mark_notification_unauthenticated(self, client, db_session):
        """Req 7.2: Unauthenticated request is rejected."""
        resp = client.put("/api/notifications/1/read")
        assert resp.status_code in (401, 403)

    def test_mark_notification_persists_in_db(self, client, db_session):
        """Req 7.2: Marking as read is persisted in the database."""
        user = _create_verified_user(db_session)
        capsule = _create_capsule(db_session, user.id)
        notif = _create_notification(db_session, user.id, capsule.id)

        client.put(f"/api/notifications/{notif.id}/read", headers=_auth_header(user.id))

        db_session.expire_all()
        updated = db_session.query(Notification).filter(Notification.id == notif.id).first()
        assert updated.is_read is True
