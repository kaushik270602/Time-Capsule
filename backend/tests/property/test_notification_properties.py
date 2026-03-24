# Feature: timelock
# Property-based tests for notification system

import pytest
from hypothesis import given, strategies as st, settings
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.user import User
from app.models.capsule import Capsule
from app.models.unlock_log import UnlockLog
from app.models.notification import Notification
from app.services.notification_service import NotificationService
from app.services.email_notifier import EmailNotifier
from app.services.push_notifier import PushNotifier
from app.services.in_app_notifier import InAppNotifier


# Context manager for database sessions (compatible with Hypothesis)
@contextmanager
def get_db_session():
    """Create a fresh database session for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


# Helper strategies
def valid_title_strategy():
    """Generate valid capsule titles"""
    return st.text(min_size=1, max_size=255).filter(lambda t: t.strip() != "")


def valid_email_strategy():
    """Generate valid email addresses"""
    return st.emails()


def create_unlocked_capsule(db_session, user, title):
    """Helper to create an unlocked capsule with proper timestamps"""
    # Set created_at in the past to satisfy check_future_unlock_date constraint
    created_at = datetime.now(timezone.utc) - timedelta(days=7)
    unlock_date = datetime.now(timezone.utc) - timedelta(hours=1)
    capsule = Capsule(
        user_id=user.id,
        title=title,
        text_content="Test content",
        unlock_date=unlock_date,
        status="unlocked",
        is_public=False,
        created_at=created_at
    )
    db_session.add(capsule)
    db_session.commit()
    return capsule


# Property 26: Unlock notifications are sent through all channels
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    email=valid_email_strategy(),
    title=valid_title_strategy()
)
def test_property_26_unlock_notifications_sent_through_all_channels(user_id, email, title):
    """
    **Property 26: Unlock notifications are sent through all channels**
    
    For any capsule unlock event, the system should send an email notification,
    create an in-app notification, and (if enabled) send a push notification
    to the capsule owner.
    
    **Validates: Requirements 7.1, 7.2, 7.3**
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule
        capsule = create_unlocked_capsule(db_session, user, title)
        
        # Mock the notification services to track calls
        with patch.object(EmailNotifier, 'send_email', return_value=True) as mock_email, \
             patch.object(PushNotifier, 'send_push', return_value=True) as mock_push:
            
            # Create notification service and send notifications
            notification_service = NotificationService(db_session)
            notification_service.notify_unlock(capsule.id)
            
            # Verify email notification was attempted
            mock_email.assert_called_once()
            
            # Verify push notification was attempted
            mock_push.assert_called_once()
            
            # Verify in-app notification was created
            in_app_notification = db_session.query(Notification).filter(
                Notification.capsule_id == capsule.id,
                Notification.user_id == user.id
            ).first()
            
            assert in_app_notification is not None, "In-app notification should be created"
            assert not in_app_notification.is_read, "New notification should be unread"


# Property 27: Notifications contain required information
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    email=valid_email_strategy(),
    title=valid_title_strategy()
)
def test_property_27_notifications_contain_required_information(user_id, email, title):
    """
    **Property 27: Notifications contain required information**
    
    For any unlock notification sent through any channel, the notification
    should include the capsule title, unlock date, and a direct link to
    view the capsule.
    
    **Validates: Requirements 7.6, 7.7**
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule
        capsule = create_unlocked_capsule(db_session, user, title)
        
        # Test in-app notification content
        in_app_notifier = InAppNotifier(db_session)
        success = in_app_notifier.create_in_app_notification(user, capsule)
        
        assert success, "In-app notification should be created successfully"
        
        # Verify notification contains required information
        notification = db_session.query(Notification).filter(
            Notification.capsule_id == capsule.id
        ).first()
        
        assert notification is not None, "Notification should exist"
        assert title in notification.message, "Notification should contain capsule title"
        # The message should reference the unlock date
        assert "unlock" in notification.message.lower(), "Notification should mention unlock"
        
        # Test email notification content
        email_notifier = EmailNotifier()
        text_body = email_notifier._create_text_body(user, capsule)
        html_body = email_notifier._create_html_body(user, capsule)
        
        # Verify email contains required information
        assert title in text_body, "Email should contain capsule title"
        assert title in html_body, "HTML email should contain capsule title"
        assert f"capsules/{capsule.id}" in text_body, "Email should contain capsule link"
        assert f"capsules/{capsule.id}" in html_body, "HTML email should contain capsule link"
        
        # Test push notification content
        push_notifier = PushNotifier()
        push_payload = push_notifier._create_push_payload(capsule)
        
        assert title in push_payload['body'], "Push notification should contain capsule title"
        assert capsule.id == push_payload['data']['capsule_id'], "Push should contain capsule ID"
        assert f"capsules/{capsule.id}" in push_payload['click_action'], "Push should contain capsule link"


# Property 28: Notification delivery is logged
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    email=valid_email_strategy(),
    title=valid_title_strategy(),
    email_success=st.booleans(),
    push_success=st.booleans()
)
def test_property_28_notification_delivery_is_logged(user_id, email, title, email_success, push_success):
    """
    **Property 28: Notification delivery is logged**
    
    For any notification sent, the system should record the delivery status
    (email_sent, push_sent, notification_sent) in the Unlock_Log.
    
    **Validates: Requirements 7.4**
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule
        capsule = create_unlocked_capsule(db_session, user, title)
        
        # Create unlock log entry
        unlock_log = UnlockLog(capsule_id=capsule.id)
        db_session.add(unlock_log)
        db_session.commit()
        
        # Mock the notification services with specified success values
        with patch.object(EmailNotifier, 'send_email', return_value=email_success) as mock_email, \
             patch.object(PushNotifier, 'send_push', return_value=push_success) as mock_push:
            
            # Create notification service and send notifications
            notification_service = NotificationService(db_session)
            notification_service.notify_unlock(capsule.id)
            
            # Refresh unlock_log to get updated values
            db_session.refresh(unlock_log)
            
            # Verify delivery status is logged
            assert unlock_log.email_sent == email_success, "Email delivery status should be logged"
            assert unlock_log.push_sent == push_success, "Push delivery status should be logged"
            # In-app notification should always succeed (unless DB error)
            assert unlock_log.notification_sent == True, "In-app notification status should be logged"


# Property 29: Failed email notifications are retried
@settings(max_examples=10, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    email=valid_email_strategy(),
    title=valid_title_strategy()
)
def test_property_29_failed_email_notifications_are_retried(user_id, email, title):
    """
    **Property 29: Failed email notifications are retried**
    
    For any email notification that fails to send, the system should retry
    delivery up to three times before marking as failed.
    
    **Validates: Requirements 7.5**
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule
        capsule = create_unlocked_capsule(db_session, user, title)
        
        # Mock email sending to fail all attempts
        email_notifier = EmailNotifier()
        with patch.object(email_notifier, '_send_email_attempt', return_value=False) as mock_send:
            # Attempt to send email
            success = email_notifier.send_email(user, capsule)
            
            # Verify it failed
            assert not success, "Email should fail when all attempts fail"
            
            # Verify it was retried 3 times (max_retries)
            assert mock_send.call_count == 3, "Email should be retried 3 times"
        
        # Test scenario where it succeeds on second attempt
        with patch.object(email_notifier, '_send_email_attempt', side_effect=[False, True]) as mock_send:
            # Attempt to send email
            success = email_notifier.send_email(user, capsule)
            
            # Verify it succeeded
            assert success, "Email should succeed when retry succeeds"
            
            # Verify it was called twice (failed once, succeeded on second)
            assert mock_send.call_count == 2, "Email should stop retrying after success"

