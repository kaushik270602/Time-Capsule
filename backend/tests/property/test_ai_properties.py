# Feature: timelock
# Property-based tests for AI analysis

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
from app.models.ai_analysis import AIAnalysis
from app.services.ai_service import AIService


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


def text_content_strategy():
    """Generate text content for capsules"""
    return st.text(min_size=10, max_size=1000)


def transcription_list_strategy():
    """Generate lists of transcriptions"""
    return st.lists(
        st.text(min_size=10, max_size=500),
        min_size=0,
        max_size=5
    )


def past_datetime_strategy():
    """Generate past datetimes in UTC"""
    return st.integers(min_value=3600, max_value=365 * 24 * 3600).map(
        lambda seconds: datetime.now(timezone.utc) - timedelta(seconds=seconds)
    )


# Property 36: AI summary is generated on unlock
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    title=valid_title_strategy(),
    text_content=text_content_strategy(),
    days_ago=st.integers(min_value=1, max_value=365)
)
def test_property_36_ai_summary_generated_on_unlock(user_id, title, text_content, days_ago):
    """
    Property 36: AI summary is generated on unlock
    
    For any capsule that unlocks, the system should generate an AI summary
    and store it in the AI_Analysis table linked to the capsule.
    
    Validates: Requirements 10.1, 10.4
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule
        created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        unlock_date = datetime.now(timezone.utc) - timedelta(hours=1)
        
        capsule = Capsule(
            user_id=user.id,
            title=title,
            text_content=text_content,
            unlock_date=unlock_date,
            status="unlocked",
            is_public=False,
            media_urls=[],
            transcriptions=[],
            created_at=created_at
        )
        db_session.add(capsule)
        db_session.commit()
        db_session.refresh(capsule)
        
        # Mock the AI services to avoid actual API calls
        with patch('app.services.ai_service.TranscriptionService') as mock_trans_service, \
             patch('app.services.ai_service.SummaryGenerator') as mock_summary_gen:
            
            mock_trans_instance = Mock()
            mock_trans_service.return_value = mock_trans_instance
            
            mock_summary_instance = Mock()
            mock_summary_instance.generate_summary.return_value = f"Summary of: {text_content[:50]}..."
            mock_summary_gen.return_value = mock_summary_instance
            
            # Create AI service and analyze capsule
            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)
            
            # Verify AI analysis was created
            assert ai_analysis is not None, "AI analysis should be created"
            assert ai_analysis.capsule_id == capsule.id, \
                "AI analysis should be linked to the capsule"
            assert ai_analysis.summary is not None, \
                "AI analysis should contain a summary"
            assert len(ai_analysis.summary) > 0, \
                "Summary should not be empty"
            
            # Verify AI analysis is stored in database
            stored_analysis = db_session.query(AIAnalysis).filter(
                AIAnalysis.capsule_id == capsule.id
            ).first()
            assert stored_analysis is not None, \
                "AI analysis should be stored in database"
            assert stored_analysis.id == ai_analysis.id, \
                "Stored analysis should match returned analysis"


# Property 37: AI summaries include temporal context
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    title=valid_title_strategy(),
    text_content=text_content_strategy(),
    days_ago=st.integers(min_value=1, max_value=365)
)
def test_property_37_ai_summaries_include_temporal_context(user_id, title, text_content, days_ago):
    """
    Property 37: AI summaries include temporal context
    
    For any AI summary generated, the summary should reference the time elapsed
    between capsule creation and unlock.
    
    Validates: Requirements 10.2
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule with specific creation date
        created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        unlock_date = datetime.now(timezone.utc) - timedelta(hours=1)
        
        capsule = Capsule(
            user_id=user.id,
            title=title,
            text_content=text_content,
            unlock_date=unlock_date,
            status="unlocked",
            is_public=False,
            media_urls=[],
            transcriptions=[],
            created_at=created_at
        )
        db_session.add(capsule)
        db_session.commit()
        db_session.refresh(capsule)
        
        # Mock the summary generator to capture the call
        with patch('app.services.ai_service.TranscriptionService') as mock_trans_service, \
             patch('app.services.ai_service.SummaryGenerator') as mock_summary_gen:
            
            mock_trans_instance = Mock()
            mock_trans_service.return_value = mock_trans_instance
            
            mock_summary_instance = Mock()
            
            # Capture the arguments passed to generate_summary
            captured_args = {}
            def capture_and_return(*args, **kwargs):
                captured_args.update(kwargs)
                return f"Summary with temporal context: {days_ago} days"
            
            mock_summary_instance.generate_summary.side_effect = capture_and_return
            mock_summary_gen.return_value = mock_summary_instance
            
            # Create AI service and analyze capsule
            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)
            
            # Verify generate_summary was called with temporal context
            assert 'created_at' in captured_args, \
                "generate_summary should receive created_at timestamp"
            assert 'unlocked_at' in captured_args, \
                "generate_summary should receive unlocked_at timestamp"
            
            # Verify the timestamps are different (time has elapsed)
            created = captured_args['created_at']
            unlocked = captured_args['unlocked_at']
            
            # Ensure both are timezone-aware for comparison
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if unlocked.tzinfo is None:
                unlocked = unlocked.replace(tzinfo=timezone.utc)
            
            assert unlocked > created, \
                "Unlock time should be after creation time"
            
            # Verify the time difference is approximately correct
            time_diff = (unlocked - created).days
            # Allow some tolerance for test execution time
            assert abs(time_diff - days_ago) <= 1, \
                f"Time difference should be approximately {days_ago} days"


# Property 38: AI summaries include transcriptions
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    title=valid_title_strategy(),
    text_content=text_content_strategy(),
    transcriptions=transcription_list_strategy()
)
def test_property_38_ai_summaries_include_transcriptions(user_id, title, text_content, transcriptions):
    """
    Property 38: AI summaries include transcriptions
    
    For any capsule with transcribed audio or video content, the transcription
    text should be included in the AI summary generation.
    
    Validates: Requirements 10.3
    """
    # Skip if no transcriptions
    if not transcriptions:
        return
    
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule with transcriptions
        created_at = datetime.now(timezone.utc) - timedelta(days=30)
        unlock_date = datetime.now(timezone.utc) - timedelta(hours=1)
        
        capsule = Capsule(
            user_id=user.id,
            title=title,
            text_content=text_content,
            unlock_date=unlock_date,
            status="unlocked",
            is_public=False,
            media_urls=[],
            transcriptions=transcriptions,
            created_at=created_at
        )
        db_session.add(capsule)
        db_session.commit()
        db_session.refresh(capsule)
        
        # Mock the summary generator to capture the call
        with patch('app.services.ai_service.TranscriptionService') as mock_trans_service, \
             patch('app.services.ai_service.SummaryGenerator') as mock_summary_gen:
            
            mock_trans_instance = Mock()
            mock_trans_service.return_value = mock_trans_instance
            
            mock_summary_instance = Mock()
            
            # Capture the arguments passed to generate_summary
            captured_args = {}
            def capture_and_return(*args, **kwargs):
                captured_args.update(kwargs)
                return "Summary including transcriptions"
            
            mock_summary_instance.generate_summary.side_effect = capture_and_return
            mock_summary_gen.return_value = mock_summary_instance
            
            # Create AI service and analyze capsule
            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)
            
            # Verify generate_summary was called with transcriptions
            assert 'transcriptions' in captured_args, \
                "generate_summary should receive transcriptions"
            
            received_transcriptions = captured_args['transcriptions']
            assert isinstance(received_transcriptions, list), \
                "Transcriptions should be passed as a list"
            assert len(received_transcriptions) == len(transcriptions), \
                f"Should receive all {len(transcriptions)} transcriptions"
            
            # Verify the transcriptions match
            for i, transcription in enumerate(transcriptions):
                assert transcription in received_transcriptions, \
                    f"Transcription {i} should be included"


# Property 39: AI summary failures are graceful
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    title=valid_title_strategy(),
    text_content=text_content_strategy()
)
def test_property_39_ai_summary_failures_are_graceful(user_id, title, text_content):
    """
    Property 39: AI summary failures are graceful
    
    For any AI summary generation that fails, the system should log the error
    and still allow capsule access without the summary.
    
    Validates: Requirements 10.5
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule
        created_at = datetime.now(timezone.utc) - timedelta(days=30)
        unlock_date = datetime.now(timezone.utc) - timedelta(hours=1)
        
        capsule = Capsule(
            user_id=user.id,
            title=title,
            text_content=text_content,
            unlock_date=unlock_date,
            status="unlocked",
            is_public=False,
            media_urls=[],
            transcriptions=[],
            created_at=created_at
        )
        db_session.add(capsule)
        db_session.commit()
        db_session.refresh(capsule)
        
        # Mock the summary generator to simulate failure
        with patch('app.services.ai_service.TranscriptionService') as mock_trans_service, \
             patch('app.services.ai_service.SummaryGenerator') as mock_summary_gen:
            
            mock_trans_instance = Mock()
            mock_trans_service.return_value = mock_trans_instance
            
            mock_summary_instance = Mock()
            # Simulate API failure by returning None
            mock_summary_instance.generate_summary.return_value = None
            mock_summary_gen.return_value = mock_summary_instance
            
            # Create AI service and analyze capsule
            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)
            
            # Verify AI analysis is still created even with failure
            assert ai_analysis is not None, \
                "AI analysis should be created even when summary generation fails"
            assert ai_analysis.capsule_id == capsule.id, \
                "AI analysis should be linked to the capsule"
            
            # Verify summary is None (indicating failure)
            assert ai_analysis.summary is None, \
                "Summary should be None when generation fails"
            
            # Verify AI analysis is stored in database
            stored_analysis = db_session.query(AIAnalysis).filter(
                AIAnalysis.capsule_id == capsule.id
            ).first()
            assert stored_analysis is not None, \
                "AI analysis should be stored even with failed summary"
            assert stored_analysis.summary is None, \
                "Stored summary should be None when generation fails"
        
        # Verify capsule is still accessible (not affected by AI failure)
        db_session.refresh(capsule)
        assert capsule.status == "unlocked", \
            "Capsule should remain unlocked despite AI failure"
        assert capsule.text_content == text_content, \
            "Capsule content should be accessible despite AI failure"


# Property 39 (Extended): AI service handles exceptions gracefully
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    title=valid_title_strategy(),
    text_content=text_content_strategy()
)
def test_property_39_ai_service_handles_exceptions_gracefully(user_id, title, text_content):
    """
    Property 39 (Extended): AI service handles exceptions gracefully
    
    For any exception that occurs during AI analysis (API errors, network errors,
    etc.), the system should catch the exception, log it, and return None without
    crashing, allowing the capsule to remain accessible.
    
    Validates: Requirements 10.5
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create an unlocked capsule
        created_at = datetime.now(timezone.utc) - timedelta(days=30)
        unlock_date = datetime.now(timezone.utc) - timedelta(hours=1)
        
        capsule = Capsule(
            user_id=user.id,
            title=title,
            text_content=text_content,
            unlock_date=unlock_date,
            status="unlocked",
            is_public=False,
            media_urls=[],
            transcriptions=[],
            created_at=created_at
        )
        db_session.add(capsule)
        db_session.commit()
        db_session.refresh(capsule)
        
        # Mock the summary generator to raise an exception
        with patch('app.services.ai_service.TranscriptionService') as mock_trans_service, \
             patch('app.services.ai_service.SummaryGenerator') as mock_summary_gen:
            
            mock_trans_instance = Mock()
            mock_trans_service.return_value = mock_trans_instance
            
            mock_summary_instance = Mock()
            # Simulate API exception
            mock_summary_instance.generate_summary.side_effect = Exception("API Error")
            mock_summary_gen.return_value = mock_summary_instance
            
            # Create AI service and analyze capsule
            ai_service = AIService()
            
            # Should not raise exception - should handle gracefully
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)
            
            # Verify AI analysis returns None on exception
            assert ai_analysis is None, \
                "AI analysis should return None when exception occurs"
        
        # Verify capsule is still accessible
        db_session.refresh(capsule)
        assert capsule.status == "unlocked", \
            "Capsule should remain unlocked despite AI exception"
        assert capsule.text_content == text_content, \
            "Capsule content should be accessible despite AI exception"


# Property 36 (Extended): AI analysis only runs on unlocked capsules
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    title=valid_title_strategy(),
    text_content=text_content_strategy()
)
def test_property_36_ai_analysis_only_on_unlocked_capsules(user_id, title, text_content):
    """
    Property 36 (Extended): AI analysis only runs on unlocked capsules
    
    For any capsule that is still locked, attempting to run AI analysis should
    be rejected or skipped, ensuring analysis only happens after unlock.
    
    Validates: Requirements 10.1
    """
    with get_db_session() as db_session:
        # Create a user
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()
        
        # Create a LOCKED capsule (future unlock date)
        created_at = datetime.now(timezone.utc) - timedelta(days=1)
        unlock_date = datetime.now(timezone.utc) + timedelta(days=30)
        
        capsule = Capsule(
            user_id=user.id,
            title=title,
            text_content=text_content,
            unlock_date=unlock_date,
            status="locked",  # Still locked
            is_public=False,
            media_urls=[],
            transcriptions=[],
            created_at=created_at
        )
        db_session.add(capsule)
        db_session.commit()
        db_session.refresh(capsule)
        
        # Mock the AI services
        with patch('app.services.ai_service.TranscriptionService') as mock_trans_service, \
             patch('app.services.ai_service.SummaryGenerator') as mock_summary_gen:
            
            mock_trans_instance = Mock()
            mock_trans_service.return_value = mock_trans_instance
            
            mock_summary_instance = Mock()
            mock_summary_instance.generate_summary.return_value = "This should not be called"
            mock_summary_gen.return_value = mock_summary_instance
            
            # Create AI service and attempt to analyze locked capsule
            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)
            
            # Verify AI analysis was not performed on locked capsule
            assert ai_analysis is None, \
                "AI analysis should not be performed on locked capsules"
            
            # Verify summary generator was not called
            mock_summary_instance.generate_summary.assert_not_called()
            
            # Verify no AI analysis record was created
            stored_analysis = db_session.query(AIAnalysis).filter(
                AIAnalysis.capsule_id == capsule.id
            ).first()
            assert stored_analysis is None, \
                "No AI analysis should be stored for locked capsules"
