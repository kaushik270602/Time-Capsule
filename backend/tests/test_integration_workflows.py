"""
Integration tests for complete TimeLock workflows.

Tests end-to-end flows:
1. Capsule lifecycle: register → login → create → lock → unlock → view
2. Unlock workflow: scheduler → AI analysis → notifications
3. Public capsule workflow: create → unlock → appear in feed

Validates: All requirements (cross-cutting integration)

Database setup and shared fixtures (client, db_session, setup_shared_db)
are provided by tests/conftest.py.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.capsule import Capsule
from app.models.notification import Notification
from app.models.unlock_log import UnlockLog
from app.models.ai_analysis import AIAnalysis
from app.models.user import User
from app.utils.jwt import JWTManager
from app.utils.password import PasswordHasher
from app.services.unlock_orchestrator import UnlockOrchestrator
from app.services.notification_service import NotificationService
from app.services.ai_service import AIService

# Import the actual rate_limiter module (not the middleware package)
import importlib
_rl_mod = importlib.import_module("app.middleware.rate_limiter")

CSRF_TOKEN = "test-csrf-token"


# ---------------------------------------------------------------------------
# Force in-memory rate limiter backend (no Redis needed)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _force_in_memory_rate_limiter():
    """Ensure the rate limiter uses the in-memory backend for all tests."""
    _rl_mod._backend = _rl_mod._InMemoryBackend()
    yield
    _rl_mod._backend = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_header(user_id: int) -> dict:
    """Build Authorization + CSRF headers for an authenticated request."""
    token = JWTManager.create_token(user_id)
    return {"Authorization": f"Bearer {token}", "X-CSRF-Token": CSRF_TOKEN}


def _create_verified_user(db, email="user@example.com", password="Password1") -> User:
    """Create a verified user directly in the DB."""
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


def _create_capsule_in_db(
    db,
    user_id: int,
    title: str = "Test Capsule",
    text_content: str = "Hello from the past!",
    unlock_date: datetime = None,
    status: str = "locked",
    is_public: bool = False,
) -> Capsule:
    """
    Create a capsule directly in the DB, bypassing the API.

    For capsules that need a past unlock_date (e.g. to test unlocking),
    we also set created_at far enough in the past to satisfy the
    CHECK constraint ``unlock_date > created_at``.
    """
    now = datetime.now(timezone.utc)
    if unlock_date is None:
        unlock_date = now + timedelta(days=30)

    # Ensure created_at is always before unlock_date to satisfy the DB constraint
    if unlock_date <= now:
        created_at = unlock_date - timedelta(days=1)
    else:
        created_at = now

    capsule = Capsule(
        user_id=user_id,
        title=title,
        text_content=text_content,
        unlock_date=unlock_date,
        status=status,
        is_public=is_public,
        media_urls=[],
        transcriptions=[],
        created_at=created_at,
    )
    db.add(capsule)
    db.commit()
    db.refresh(capsule)
    return capsule


@pytest.fixture
def csrf_client():
    """TestClient with CSRF cookie pre-set."""
    c = TestClient(app)
    c.cookies.set("csrf_token", CSRF_TOKEN)
    return c


# =========================================================================
# 1. Capsule Lifecycle: register → login → create → lock → unlock → view
# =========================================================================


class TestCapsuleLifecycle:
    """End-to-end capsule lifecycle through the API."""

    @patch("app.routers.capsules.cache_get", return_value=None)
    @patch("app.routers.capsules.cache_set", return_value=True)
    @patch("app.routers.capsules.invalidate_capsule_caches")
    def test_full_lifecycle_via_api(
        self, mock_inv, mock_cset, mock_cget, csrf_client, db_session
    ):
        """
        Register a user, login, create a capsule, verify it's locked,
        simulate unlock (update status directly), then verify content
        is accessible.
        """
        client = csrf_client

        # --- Step 1: Register ---
        reg_resp = client.post("/api/auth/register", json={
            "email": "lifecycle@example.com",
            "password": "StrongPass1",
        })
        assert reg_resp.status_code == 201
        assert reg_resp.json()["email"] == "lifecycle@example.com"

        # Manually verify the user so we can log in
        user = db_session.query(User).filter(
            User.email == "lifecycle@example.com"
        ).first()
        user.is_verified = True
        db_session.commit()

        # --- Step 2: Login ---
        login_resp = client.post("/api/auth/login", json={
            "email": "lifecycle@example.com",
            "password": "StrongPass1",
        })
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": CSRF_TOKEN}

        # --- Step 3: Create capsule ---
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = client.post("/api/capsules", json={
            "title": "My Time Capsule",
            "text_content": "A message from the past",
            "unlock_date": future_date,
            "is_public": False,
        }, headers=headers)
        assert create_resp.status_code == 201
        capsule_data = create_resp.json()
        capsule_id = capsule_data["id"]
        assert capsule_data["status"] == "locked"
        # Content should be hidden for a newly created (locked) capsule
        assert capsule_data["text_content"] is None

        # --- Step 4: Verify capsule is locked via GET ---
        get_resp = client.get(f"/api/capsules/{capsule_id}", headers=headers)
        assert get_resp.status_code == 200
        locked_data = get_resp.json()
        assert locked_data["status"] == "locked"
        assert locked_data["text_content"] is None

        # --- Step 5: Simulate unlock (update status directly in DB) ---
        capsule = db_session.query(Capsule).filter(Capsule.id == capsule_id).first()
        capsule.status = "unlocked"
        db_session.commit()

        # --- Step 6: Verify content is now accessible ---
        get_resp2 = client.get(f"/api/capsules/{capsule_id}", headers=headers)
        assert get_resp2.status_code == 200
        unlocked_data = get_resp2.json()
        assert unlocked_data["status"] == "unlocked"
        assert unlocked_data["text_content"] == "A message from the past"

    @patch("app.routers.capsules.cache_get", return_value=None)
    @patch("app.routers.capsules.cache_set", return_value=True)
    @patch("app.routers.capsules.invalidate_capsule_caches")
    def test_locked_capsule_hides_content_via_get(
        self, mock_inv, mock_cset, mock_cget, csrf_client, db_session
    ):
        """Locked capsule GET endpoint returns metadata only, no content."""
        user = _create_verified_user(db_session, email="listuser@example.com")
        capsule = _create_capsule_in_db(
            db_session, user.id, title="Secret", text_content="Hidden"
        )

        headers = _auth_header(user.id)
        resp = csrf_client.get(f"/api/capsules/{capsule.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Secret"
        assert data["status"] == "locked"
        # Locked capsule should not expose text_content
        assert data["text_content"] is None


# =========================================================================
# 2. Unlock Workflow: orchestrator → AI analysis → notifications
# =========================================================================


class TestUnlockWorkflow:
    """
    Tests the unlock orchestrator flow: capsule with past unlock date
    is processed, status changes, AI analysis is triggered, and
    notifications are sent.
    """

    @patch("app.services.unlock_orchestrator.invalidate_capsule_caches")
    @patch("app.services.unlock_orchestrator.UnlockOrchestrator._trigger_notifications")
    @patch("app.services.unlock_orchestrator.UnlockOrchestrator._trigger_ai_analysis")
    def test_orchestrator_unlocks_past_due_capsule(
        self, mock_ai, mock_notif, mock_cache, db_session
    ):
        """
        A capsule whose unlock_date is in the past should be unlocked
        by the orchestrator, with AI analysis and notifications triggered.
        """
        from sqlalchemy.orm import Query
        from unittest.mock import PropertyMock

        user = _create_verified_user(db_session, email="unlock@example.com")
        past_unlock = datetime.now(timezone.utc) - timedelta(hours=1)
        capsule = _create_capsule_in_db(
            db_session,
            user.id,
            title="Past Due",
            text_content="Unlock me",
            unlock_date=past_unlock,
        )
        assert capsule.status == "locked"

        # SQLite strips timezone info, so the orchestrator's comparison
        # of naive (from DB) vs aware (datetime.now(tz)) fails.
        # We patch datetime in the orchestrator module to return naive UTC.
        import app.services.unlock_orchestrator as orch_mod
        _real_datetime = datetime

        class _NaiveDatetime(_real_datetime):
            @classmethod
            def now(cls, tz=None):
                return _real_datetime.utcnow()

        orchestrator = UnlockOrchestrator()
        with patch.object(Query, "with_for_update", lambda self, **kw: self), \
             patch.object(orch_mod, "datetime", _NaiveDatetime):
            result = orchestrator.process_unlock(capsule.id, db=db_session)

        assert result is True

        # Refresh to see DB changes
        db_session.refresh(capsule)
        assert capsule.status == "unlocked"

        # Unlock log should be created
        log = db_session.query(UnlockLog).filter(
            UnlockLog.capsule_id == capsule.id
        ).first()
        assert log is not None
        assert log.unlocked_at is not None

        # AI analysis and notifications should have been triggered
        mock_ai.assert_called_once_with(capsule.id)
        mock_notif.assert_called_once_with(capsule.id)

    @patch("app.services.unlock_orchestrator.invalidate_capsule_caches")
    @patch("app.services.unlock_orchestrator.UnlockOrchestrator._trigger_notifications")
    @patch("app.services.unlock_orchestrator.UnlockOrchestrator._trigger_ai_analysis")
    def test_orchestrator_skips_already_unlocked(
        self, mock_ai, mock_notif, mock_cache, db_session
    ):
        """Already-unlocked capsules are skipped gracefully."""
        from sqlalchemy.orm import Query

        user = _create_verified_user(db_session, email="skip@example.com")
        capsule = _create_capsule_in_db(
            db_session,
            user.id,
            unlock_date=datetime.now(timezone.utc) - timedelta(hours=1),
            status="unlocked",
        )

        orchestrator = UnlockOrchestrator()
        with patch.object(Query, "with_for_update", lambda self, **kw: self):
            result = orchestrator.process_unlock(capsule.id, db=db_session)

        # Should return True (already unlocked) but not trigger side effects
        assert result is True
        mock_ai.assert_not_called()
        mock_notif.assert_not_called()

    @patch("app.services.unlock_orchestrator.invalidate_capsule_caches")
    @patch("app.services.unlock_orchestrator.UnlockOrchestrator._trigger_notifications")
    @patch("app.services.unlock_orchestrator.UnlockOrchestrator._trigger_ai_analysis")
    def test_orchestrator_rejects_future_capsule(
        self, mock_ai, mock_notif, mock_cache, db_session
    ):
        """Capsules whose unlock_date hasn't arrived yet are not unlocked."""
        from sqlalchemy.orm import Query

        user = _create_verified_user(db_session, email="future@example.com")
        capsule = _create_capsule_in_db(
            db_session,
            user.id,
            unlock_date=datetime.now(timezone.utc) + timedelta(days=30),
        )

        orchestrator = UnlockOrchestrator()
        with patch.object(Query, "with_for_update", lambda self, **kw: self):
            result = orchestrator.process_unlock(capsule.id, db=db_session)

        assert result is False
        db_session.refresh(capsule)
        assert capsule.status == "locked"
        mock_ai.assert_not_called()
        mock_notif.assert_not_called()

    def test_notification_service_creates_in_app_notification(self, db_session):
        """
        After unlock, the notification service creates an in-app notification
        and logs delivery status.
        """
        user = _create_verified_user(db_session, email="notif@example.com")
        capsule = _create_capsule_in_db(
            db_session,
            user.id,
            title="Notify Me",
            unlock_date=datetime.now(timezone.utc) - timedelta(hours=1),
            status="unlocked",
        )
        # Create an unlock log entry (normally done by orchestrator)
        unlock_log = UnlockLog(capsule_id=capsule.id)
        db_session.add(unlock_log)
        db_session.commit()

        # Mock external notifiers but let in-app work against real DB
        with patch("app.services.notification_service.EmailNotifier") as MockEmail, \
             patch("app.services.notification_service.PushNotifier") as MockPush:
            MockEmail.return_value.send_email.return_value = True
            MockPush.return_value.send_push.return_value = False

            svc = NotificationService(db_session)
            svc.notify_unlock(capsule.id)

        # In-app notification should exist
        notif = db_session.query(Notification).filter(
            Notification.capsule_id == capsule.id
        ).first()
        assert notif is not None
        assert notif.user_id == user.id
        assert "Notify Me" in notif.message

        # Unlock log should be updated with delivery status
        db_session.refresh(unlock_log)
        assert unlock_log.email_sent is True
        assert unlock_log.notification_sent is True  # in-app

    def test_ai_service_stores_analysis(self, db_session):
        """
        AI service generates a summary and stores it in the AI_Analysis table.
        """
        user = _create_verified_user(db_session, email="ai@example.com")
        capsule = _create_capsule_in_db(
            db_session,
            user.id,
            title="AI Test",
            text_content="Remember this moment",
            unlock_date=datetime.now(timezone.utc) - timedelta(hours=1),
            status="unlocked",
        )

        with patch("app.services.ai_service.SummaryGenerator") as MockSummary, \
             patch("app.services.ai_service.TranscriptionService") as MockTranscription, \
             patch("app.services.ai_service.SentimentDetector") as MockSentiment, \
             patch("app.services.ai_service.VisionAnalyzer") as MockVision, \
             patch("app.services.ai_service.RecapGenerator") as MockRecap:
            MockSummary.return_value.generate_summary.return_value = (
                "A heartfelt message created 1 hour ago."
            )
            MockTranscription.return_value.transcribe_media.return_value = None
            MockSentiment.return_value.detect_sentiment.return_value = {
                "label": "nostalgic", "confidence": 0.85, "tone_description": "A reflective tone"
            }
            MockVision.return_value.analyze_images.return_value = []
            MockRecap.return_value.generate_recap.return_value = "A beautiful recap of your memory."

            ai_svc = AIService()
            analysis = ai_svc.analyze_capsule(capsule.id, db_session)

        assert analysis is not None
        assert analysis.capsule_id == capsule.id
        assert "heartfelt" in analysis.summary
        assert analysis.processing_status == "completed"

        # Verify persisted in DB
        stored = db_session.query(AIAnalysis).filter(
            AIAnalysis.capsule_id == capsule.id
        ).first()
        assert stored is not None
        assert stored.summary == analysis.summary


# =========================================================================
# 3. Public Capsule Workflow: create → unlock → appear in feed
# =========================================================================


class TestPublicCapsuleWorkflow:
    """
    Tests that public capsules appear in the public feed only after
    unlocking, and that private capsules never appear.
    """

    @patch("app.routers.capsules.cache_get", return_value=None)
    @patch("app.routers.capsules.cache_set", return_value=True)
    @patch("app.routers.capsules.invalidate_capsule_caches")
    def test_public_capsule_appears_in_feed_after_unlock(
        self, mock_inv, mock_cset, mock_cget, csrf_client, db_session
    ):
        """
        Create a public capsule, verify it's NOT in the feed while locked,
        unlock it, then verify it IS in the feed.
        """
        user = _create_verified_user(db_session, email="public@example.com")

        # Create a locked public capsule
        capsule = _create_capsule_in_db(
            db_session,
            user.id,
            title="Public Prediction",
            text_content="I predict the future!",
            is_public=True,
        )

        # Public feed should NOT contain the locked capsule
        feed_resp = csrf_client.get("/api/public/capsules")
        assert feed_resp.status_code == 200
        capsule_ids = [c["id"] for c in feed_resp.json()["capsules"]]
        assert capsule.id not in capsule_ids

        # Unlock the capsule
        capsule.status = "unlocked"
        db_session.commit()

        # Public feed should now contain the capsule
        feed_resp2 = csrf_client.get("/api/public/capsules")
        assert feed_resp2.status_code == 200
        capsule_ids2 = [c["id"] for c in feed_resp2.json()["capsules"]]
        assert capsule.id in capsule_ids2

        # Verify the feed entry has expected fields
        entry = next(c for c in feed_resp2.json()["capsules"] if c["id"] == capsule.id)
        assert entry["title"] == "Public Prediction"
        assert entry["user_id"] == user.id

    @patch("app.routers.capsules.cache_get", return_value=None)
    @patch("app.routers.capsules.cache_set", return_value=True)
    @patch("app.routers.capsules.invalidate_capsule_caches")
    def test_private_capsule_never_in_public_feed(
        self, mock_inv, mock_cset, mock_cget, csrf_client, db_session
    ):
        """Private capsules should never appear in the public feed, even when unlocked."""
        user = _create_verified_user(db_session, email="private@example.com")

        capsule = _create_capsule_in_db(
            db_session,
            user.id,
            title="Private Secret",
            text_content="Only for me",
            is_public=False,
            status="unlocked",
            unlock_date=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        feed_resp = csrf_client.get("/api/public/capsules")
        assert feed_resp.status_code == 200
        capsule_ids = [c["id"] for c in feed_resp.json()["capsules"]]
        assert capsule.id not in capsule_ids

    @patch("app.routers.capsules.cache_get", return_value=None)
    @patch("app.routers.capsules.cache_set", return_value=True)
    def test_public_feed_accessible_without_auth(
        self, mock_cset, mock_cget, csrf_client
    ):
        """The public feed endpoint does not require authentication."""
        resp = csrf_client.get("/api/public/capsules")
        assert resp.status_code == 200

    @patch("app.routers.capsules.cache_get", return_value=None)
    @patch("app.routers.capsules.cache_set", return_value=True)
    @patch("app.routers.capsules.invalidate_capsule_caches")
    def test_mixed_capsules_only_public_unlocked_in_feed(
        self, mock_inv, mock_cset, mock_cget, csrf_client, db_session
    ):
        """
        With a mix of public/private and locked/unlocked capsules,
        only public + unlocked ones appear in the feed.
        """
        user = _create_verified_user(db_session, email="mix@example.com")

        past = datetime.now(timezone.utc) - timedelta(hours=1)

        # Public locked — should NOT appear
        c1 = _create_capsule_in_db(
            db_session, user.id,
            title="Public Locked",
            is_public=True, status="locked",
        )
        # Public unlocked — SHOULD appear
        c2 = _create_capsule_in_db(
            db_session, user.id,
            title="Public Unlocked",
            is_public=True, status="unlocked",
            unlock_date=past,
        )
        # Private locked — should NOT appear
        c3 = _create_capsule_in_db(
            db_session, user.id,
            title="Private Locked",
            is_public=False, status="locked",
        )
        # Private unlocked — should NOT appear
        c4 = _create_capsule_in_db(
            db_session, user.id,
            title="Private Unlocked",
            is_public=False, status="unlocked",
            unlock_date=past,
        )

        feed_resp = csrf_client.get("/api/public/capsules")
        assert feed_resp.status_code == 200
        feed_ids = [c["id"] for c in feed_resp.json()["capsules"]]

        assert c2.id in feed_ids       # public + unlocked
        assert c1.id not in feed_ids   # public + locked
        assert c3.id not in feed_ids   # private + locked
        assert c4.id not in feed_ids   # private + unlocked

    @patch("app.routers.capsules.cache_get", return_value=None)
    @patch("app.routers.capsules.cache_set", return_value=True)
    @patch("app.routers.capsules.invalidate_capsule_caches")
    @patch("app.services.unlock_orchestrator.invalidate_capsule_caches")
    def test_full_public_capsule_flow_via_api(
        self, mock_orch_cache, mock_inv, mock_cset, mock_cget,
        csrf_client, db_session,
    ):
        """
        End-to-end: create a public capsule via API, unlock via orchestrator,
        then verify it appears in the public feed.
        """
        user = _create_verified_user(db_session, email="e2e_public@example.com")
        headers = _auth_header(user.id)

        # Create public capsule via API
        future_date = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        create_resp = csrf_client.post("/api/capsules", json={
            "title": "My Public Prediction",
            "text_content": "This will come true",
            "unlock_date": future_date,
            "is_public": True,
        }, headers=headers)
        assert create_resp.status_code == 201
        capsule_id = create_resp.json()["id"]

        # Not in feed yet (locked)
        feed_resp = csrf_client.get("/api/public/capsules")
        feed_ids = [c["id"] for c in feed_resp.json()["capsules"]]
        assert capsule_id not in feed_ids

        # Move unlock_date to the past and run orchestrator
        capsule = db_session.query(Capsule).filter(Capsule.id == capsule_id).first()
        # Must also move created_at back to satisfy CHECK(unlock_date > created_at)
        past_unlock = datetime.now(timezone.utc) - timedelta(hours=1)
        capsule.created_at = past_unlock - timedelta(days=1)
        capsule.unlock_date = past_unlock
        db_session.commit()

        with patch.object(UnlockOrchestrator, "_trigger_ai_analysis"), \
             patch.object(UnlockOrchestrator, "_trigger_notifications"):
            orchestrator = UnlockOrchestrator()
            # Patch with_for_update for SQLite and datetime for naive compat
            from sqlalchemy.orm import Query
            import app.services.unlock_orchestrator as orch_mod
            _real_datetime = datetime

            class _NaiveDatetime(_real_datetime):
                @classmethod
                def now(cls, tz=None):
                    return _real_datetime.utcnow()

            with patch.object(Query, "with_for_update", lambda self, **kw: self), \
                 patch.object(orch_mod, "datetime", _NaiveDatetime):
                result = orchestrator.process_unlock(capsule_id, db=db_session)
        assert result is True

        # Now it should appear in the public feed
        feed_resp2 = csrf_client.get("/api/public/capsules")
        feed_ids2 = [c["id"] for c in feed_resp2.json()["capsules"]]
        assert capsule_id in feed_ids2
