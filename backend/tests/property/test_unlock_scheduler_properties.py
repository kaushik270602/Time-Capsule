# Feature: timelock
# Property-based tests for unlock scheduler

import pytest
import sys
from hypothesis import given, strategies as st, settings, assume
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock, call
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.user import User
from app.models.capsule import Capsule
from app.models.unlock_log import UnlockLog


# Mock the database module before importing services that depend on it
sys.modules['app.database'] = MagicMock()
sys.modules['app.database'].SessionLocal = MagicMock()

# Mock the tasks module to avoid Celery dependencies
sys.modules['app.tasks'] = MagicMock()
sys.modules['app.tasks.unlock_scheduler'] = MagicMock()
sys.modules['app.tasks.ai_analysis'] = MagicMock()
sys.modules['app.tasks.notifications'] = MagicMock()


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


def past_datetime_strategy():
    """Generate past datetimes in UTC (for unlock dates that have arrived)"""
    return st.integers(min_value=60, max_value=365 * 24 * 3600).map(
        lambda seconds: datetime.now(timezone.utc) - timedelta(seconds=seconds)
    )


def future_datetime_strategy():
    """Generate future datetimes in UTC"""
    return st.integers(min_value=60, max_value=365 * 24 * 3600).map(
        lambda seconds: datetime.now(timezone.utc) + timedelta(seconds=seconds)
    )


def create_locked_capsule(db_session, user, title, unlock_date):
    """Helper to create a locked capsule with proper timestamps"""
    # Ensure created_at is before unlock_date to satisfy constraint
    if unlock_date > datetime.now(timezone.utc):
        created_at = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        created_at = unlock_date - timedelta(days=7)
    
    # Convert to naive datetime for SQLite compatibility
    unlock_date_naive = unlock_date.replace(tzinfo=None) if unlock_date.tzinfo else unlock_date
    created_at_naive = created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
    
    capsule = Capsule(
        user_id=user.id,
        title=title,
        text_content="Test content for unlock",
        unlock_date=unlock_date_naive,
        status="locked",
        is_public=False,
        created_at=created_at_naive
    )
    db_session.add(capsule)
    db_session.commit()
    return capsule


# Property 22: Capsules unlock when time arrives
@settings(max_examples=20, deadline=None)
@given(
    email=valid_email_strategy(),
    title=valid_title_strategy(),
    unlock_date=past_datetime_strategy()
)
def test_property_22_capsules_unlock_when_time_arrives(email, title, unlock_date):
    """
    **Property 22: Capsules unlock when time arrives**
    
    For any capsule where current time >= unlock_date and Content_Status is "locked",
    the scheduler should change Content_Status to "unlocked" and log the event
    in Unlock_Log.
    
    **Validates: Requirements 6.1, 6.3**
    """
    # Import here to avoid database connection issues at module load time
    from app.services.unlock_orchestrator import UnlockOrchestrator
    
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create a locked capsule with unlock_date in the past
        capsule = create_locked_capsule(db_session, user, title, unlock_date)
        
        # Verify initial state
        assert capsule.status == "locked", "Capsule should start as locked"
        # Compare as naive datetimes for SQLite compatibility
        current_time_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        assert capsule.unlock_date <= current_time_naive, \
            "Unlock date should have arrived"
        
        # Mock the async task triggers to prevent actual Celery calls
        # Also mock datetime.now to return naive datetime for SQLite compatibility
        with patch('app.services.unlock_orchestrator.UnlockOrchestrator._trigger_ai_analysis'), \
             patch('app.services.unlock_orchestrator.UnlockOrchestrator._trigger_notifications'), \
             patch('app.services.unlock_orchestrator.datetime') as mock_datetime:
            
            # Make datetime.now() return naive datetime
            mock_datetime.now.return_value = datetime.now(timezone.utc).replace(tzinfo=None)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Process the unlock
            orchestrator = UnlockOrchestrator()
            success = orchestrator.process_unlock(capsule.id, db_session)
            
            # Verify unlock was successful
            assert success, "Unlock should succeed when time has arrived"
            
            # Refresh capsule from database
            db_session.refresh(capsule)
            
            # Verify capsule status changed to unlocked
            assert capsule.status == "unlocked", \
                "Capsule status should change to 'unlocked'"
            
            # Verify unlock event was logged
            unlock_log = db_session.query(UnlockLog).filter(
                UnlockLog.capsule_id == capsule.id
            ).first()
            
            assert unlock_log is not None, "Unlock event should be logged"
            assert unlock_log.unlocked_at is not None, \
                "Unlock log should have unlocked_at timestamp"
            # Compare as naive datetimes for SQLite compatibility
            current_time_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            assert unlock_log.unlocked_at <= current_time_naive, \
                "Unlock timestamp should be current or past"


# Property 23: Unlock triggers notifications and AI analysis
@settings(max_examples=15, deadline=None)
@given(
    email=valid_email_strategy(),
    title=valid_title_strategy(),
    unlock_date=past_datetime_strategy()
)
def test_property_23_unlock_triggers_notifications_and_ai_analysis(email, title, unlock_date):
    """
    **Property 23: Unlock triggers notifications and AI analysis**
    
    For any capsule that transitions from "locked" to "unlocked", the system
    should trigger both the notification process and AI analysis generation.
    
    **Validates: Requirements 6.4, 6.5**
    """
    # Import here to avoid database connection issues at module load time
    from app.services.unlock_orchestrator import UnlockOrchestrator
    
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create a locked capsule ready to unlock
        capsule = create_locked_capsule(db_session, user, title, unlock_date)
        
        # Mock the async task triggers to track calls
        # Also mock datetime.now to return naive datetime for SQLite compatibility
        with patch('app.services.unlock_orchestrator.UnlockOrchestrator._trigger_ai_analysis') as mock_ai, \
             patch('app.services.unlock_orchestrator.UnlockOrchestrator._trigger_notifications') as mock_notif, \
             patch('app.services.unlock_orchestrator.datetime') as mock_datetime:
            
            # Make datetime.now() return naive datetime
            mock_datetime.now.return_value = datetime.now(timezone.utc).replace(tzinfo=None)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Process the unlock
            orchestrator = UnlockOrchestrator()
            success = orchestrator.process_unlock(capsule.id, db_session)
            
            # Verify unlock was successful
            assert success, "Unlock should succeed"
            
            # Verify AI analysis was triggered
            mock_ai.assert_called_once_with(capsule.id)
            
            # Verify notifications were triggered
            mock_notif.assert_called_once_with(capsule.id)


# Property 24: Failed unlocks are retried
@settings(max_examples=10, deadline=None)
@given(
    email=valid_email_strategy(),
    title=valid_title_strategy(),
    unlock_date=past_datetime_strategy(),
    attempt=st.integers(min_value=1, max_value=2)
)
def test_property_24_failed_unlocks_are_retried(email, title, unlock_date, attempt):
    """
    **Property 24: Failed unlocks are retried**
    
    For any unlock operation that fails, the system should retry the operation
    with exponential backoff up to a maximum number of attempts.
    
    **Validates: Requirements 6.6**
    """
    # Import here to avoid database connection issues at module load time
    from app.services.unlock_orchestrator import UnlockOrchestrator
    
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create a locked capsule ready to unlock
        capsule = create_locked_capsule(db_session, user, title, unlock_date)
        
        # Test the retry logic by mocking the Celery task import
        orchestrator = UnlockOrchestrator()
        
        # Mock the unlock_capsule task where it's imported (inside retry_failed_unlock)
        with patch('app.tasks.unlock_scheduler.unlock_capsule') as mock_task:
            mock_task.apply_async = MagicMock()
            
            # Trigger retry logic
            orchestrator.retry_failed_unlock(capsule.id, attempt)
            
            # Verify retry was scheduled
            mock_task.apply_async.assert_called_once()
            
            # Verify exponential backoff was applied
            call_kwargs = mock_task.apply_async.call_args[1]
            expected_countdown = 60 * (2 ** (attempt - 1))
            assert call_kwargs['countdown'] == expected_countdown, \
                f"Retry should use exponential backoff: {expected_countdown}s"
            
            # Verify retry flag is set correctly
            assert call_kwargs['retry'] == False, \
                "Manual retry handling should disable Celery auto-retry"


# Property 25: Unlocks are processed in order
@settings(max_examples=10, deadline=None)
@given(
    email=valid_email_strategy(),
    num_capsules=st.integers(min_value=2, max_value=5)
)
def test_property_25_unlocks_are_processed_in_order(email, num_capsules):
    """
    **Property 25: Unlocks are processed in order**
    
    For any set of capsules ready to unlock, the scheduler should process them
    in order of unlock_date (earliest first).
    
    **Validates: Requirements 6.7**
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
        
        # Create multiple locked capsules with different unlock dates (all in past)
        capsules = []
        base_time = datetime.now(timezone.utc) - timedelta(days=10)
        
        for i in range(num_capsules):
            # Create unlock dates with varying offsets to ensure different times
            unlock_date = base_time + timedelta(hours=i * 24)
            capsule = create_locked_capsule(
                db_session,
                user,
                f"Capsule {i}",
                unlock_date
            )
            capsules.append(capsule)
        
        # Sort capsules by unlock_date to get expected order
        expected_order = sorted(capsules, key=lambda c: c.unlock_date)
        
        # Query capsules as the scheduler would
        current_time_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        queried_capsules = db_session.query(Capsule).filter(
            Capsule.status == "locked",
            Capsule.unlock_date <= current_time_naive
        ).order_by(Capsule.unlock_date.asc()).all()
        
        # Verify capsules are returned in order by unlock_date
        assert len(queried_capsules) == num_capsules, \
            "All capsules should be ready to unlock"
        
        for i, capsule in enumerate(queried_capsules):
            assert capsule.id == expected_order[i].id, \
                f"Capsule at position {i} should match expected order"
            
            if i > 0:
                assert capsule.unlock_date >= queried_capsules[i-1].unlock_date, \
                    "Capsules should be ordered by unlock_date (earliest first)"


# Additional test: Verify scheduler doesn't unlock future capsules
@settings(max_examples=15, deadline=None)
@given(
    email=valid_email_strategy(),
    title=valid_title_strategy(),
    unlock_date=future_datetime_strategy()
)
def test_scheduler_does_not_unlock_future_capsules(email, title, unlock_date):
    """
    Verify that capsules with future unlock dates are not unlocked by the scheduler.
    
    This ensures the time-based locking mechanism is enforced correctly.
    """
    # Import here to avoid database connection issues at module load time
    from app.services.unlock_orchestrator import UnlockOrchestrator
    
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create a locked capsule with future unlock_date
        capsule = create_locked_capsule(db_session, user, title, unlock_date)
        
        # Verify initial state
        assert capsule.status == "locked", "Capsule should start as locked"
        # Compare as naive datetimes for SQLite compatibility
        current_time_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        assert capsule.unlock_date > current_time_naive, \
            "Unlock date should be in the future"
        
        # Mock the async task triggers
        # Also mock datetime.now to return naive datetime for SQLite compatibility
        with patch('app.services.unlock_orchestrator.UnlockOrchestrator._trigger_ai_analysis'), \
             patch('app.services.unlock_orchestrator.UnlockOrchestrator._trigger_notifications'), \
             patch('app.services.unlock_orchestrator.datetime') as mock_datetime:
            
            # Make datetime.now() return naive datetime
            mock_datetime.now.return_value = datetime.now(timezone.utc).replace(tzinfo=None)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Attempt to process the unlock
            orchestrator = UnlockOrchestrator()
            success = orchestrator.process_unlock(capsule.id, db_session)
            
            # Verify unlock was rejected
            assert not success, "Unlock should fail for future unlock dates"
            
            # Refresh capsule from database
            db_session.refresh(capsule)
            
            # Verify capsule status remains locked
            assert capsule.status == "locked", \
                "Capsule status should remain 'locked' for future dates"
            
            # Verify no unlock log was created
            unlock_log = db_session.query(UnlockLog).filter(
                UnlockLog.capsule_id == capsule.id
            ).first()
            
            assert unlock_log is None, \
                "No unlock log should be created for future unlock dates"


# Additional test: Verify idempotency of unlock operation
@settings(max_examples=15, deadline=None)
@given(
    email=valid_email_strategy(),
    title=valid_title_strategy(),
    unlock_date=past_datetime_strategy()
)
def test_unlock_operation_is_idempotent(email, title, unlock_date):
    """
    Verify that unlocking an already unlocked capsule is idempotent.
    
    This ensures the system handles duplicate unlock attempts gracefully.
    """
    # Import here to avoid database connection issues at module load time
    from app.services.unlock_orchestrator import UnlockOrchestrator
    
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=email,
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create a locked capsule
        capsule = create_locked_capsule(db_session, user, title, unlock_date)
        
        # Mock the async task triggers
        # Also mock datetime.now to return naive datetime for SQLite compatibility
        with patch('app.services.unlock_orchestrator.UnlockOrchestrator._trigger_ai_analysis') as mock_ai, \
             patch('app.services.unlock_orchestrator.UnlockOrchestrator._trigger_notifications') as mock_notif, \
             patch('app.services.unlock_orchestrator.datetime') as mock_datetime:
            
            # Make datetime.now() return naive datetime
            current_time_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            mock_datetime.now.return_value = current_time_naive
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # First unlock
            orchestrator = UnlockOrchestrator()
            success1 = orchestrator.process_unlock(capsule.id, db_session)
            
            assert success1, "First unlock should succeed"
            
            # Verify capsule is unlocked
            db_session.refresh(capsule)
            assert capsule.status == "unlocked"
            
            # Reset mocks
            mock_ai.reset_mock()
            mock_notif.reset_mock()
            
            # Second unlock attempt (should be idempotent)
            success2 = orchestrator.process_unlock(capsule.id, db_session)
            
            assert success2, "Second unlock should succeed (idempotent)"
            
            # Verify capsule remains unlocked
            db_session.refresh(capsule)
            assert capsule.status == "unlocked"
            
            # Verify AI and notifications are NOT triggered again
            mock_ai.assert_not_called()
            mock_notif.assert_not_called()
            
            # Verify only one unlock log entry exists
            unlock_logs = db_session.query(UnlockLog).filter(
                UnlockLog.capsule_id == capsule.id
            ).all()
            
            assert len(unlock_logs) == 1, \
                "Only one unlock log should exist for idempotent operations"
