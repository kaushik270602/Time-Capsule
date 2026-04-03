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


# Helper to patch all AI sub-services on the AIService module
def patch_all_ai_services():
    """Returns a combined context manager that patches all 5 AI sub-services."""
    return (
        patch('app.services.ai_service.TranscriptionService'),
        patch('app.services.ai_service.SummaryGenerator'),
        patch('app.services.ai_service.SentimentDetector'),
        patch('app.services.ai_service.VisionAnalyzer'),
        patch('app.services.ai_service.RecapGenerator'),
    )


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
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

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

        p1, p2, p3, p4, p5 = patch_all_ai_services()
        with p1 as mock_ts, p2 as mock_sg, p3 as mock_sd, p4 as mock_va, p5 as mock_rg:
            mock_ts.return_value = Mock()
            mock_sg_inst = Mock()
            mock_sg_inst.generate_summary.return_value = f"Summary of: {text_content[:50]}..."
            mock_sg.return_value = mock_sg_inst
            mock_sd.return_value = Mock(detect_sentiment=Mock(return_value={"label": "neutral", "confidence": 0.0, "tone_description": ""}))
            mock_va.return_value = Mock(analyze_images=Mock(return_value=[]))
            mock_rg.return_value = Mock(generate_recap=Mock(return_value=None))

            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)

            assert ai_analysis is not None, "AI analysis should be created"
            assert ai_analysis.capsule_id == capsule.id
            assert ai_analysis.summary is not None
            assert len(ai_analysis.summary) > 0

            stored_analysis = db_session.query(AIAnalysis).filter(
                AIAnalysis.capsule_id == capsule.id
            ).first()
            assert stored_analysis is not None
            assert stored_analysis.id == ai_analysis.id


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

    Validates: Requirements 10.2
    """
    with get_db_session() as db_session:
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

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

        p1, p2, p3, p4, p5 = patch_all_ai_services()
        with p1 as mock_ts, p2 as mock_sg, p3 as mock_sd, p4 as mock_va, p5 as mock_rg:
            mock_ts.return_value = Mock()

            mock_sg_inst = Mock()
            captured_args = {}
            def capture_and_return(*args, **kwargs):
                captured_args.update(kwargs)
                return f"Summary with temporal context: {days_ago} days"
            mock_sg_inst.generate_summary.side_effect = capture_and_return
            mock_sg.return_value = mock_sg_inst

            mock_sd.return_value = Mock(detect_sentiment=Mock(return_value={"label": "neutral", "confidence": 0.0, "tone_description": ""}))
            mock_va.return_value = Mock(analyze_images=Mock(return_value=[]))
            mock_rg.return_value = Mock(generate_recap=Mock(return_value=None))

            ai_service = AIService()
            ai_service.analyze_capsule(capsule.id, db_session)

            assert 'created_at' in captured_args
            assert 'unlocked_at' in captured_args

            created = captured_args['created_at']
            unlocked = captured_args['unlocked_at']
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if unlocked.tzinfo is None:
                unlocked = unlocked.replace(tzinfo=timezone.utc)

            assert unlocked > created
            time_diff = (unlocked - created).days
            assert abs(time_diff - days_ago) <= 1


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

    Validates: Requirements 10.3
    """
    if not transcriptions:
        return

    with get_db_session() as db_session:
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

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

        p1, p2, p3, p4, p5 = patch_all_ai_services()
        with p1 as mock_ts, p2 as mock_sg, p3 as mock_sd, p4 as mock_va, p5 as mock_rg:
            mock_ts.return_value = Mock()

            mock_sg_inst = Mock()
            captured_args = {}
            def capture_and_return(*args, **kwargs):
                captured_args.update(kwargs)
                return "Summary including transcriptions"
            mock_sg_inst.generate_summary.side_effect = capture_and_return
            mock_sg.return_value = mock_sg_inst

            mock_sd.return_value = Mock(detect_sentiment=Mock(return_value={"label": "neutral", "confidence": 0.0, "tone_description": ""}))
            mock_va.return_value = Mock(analyze_images=Mock(return_value=[]))
            mock_rg.return_value = Mock(generate_recap=Mock(return_value=None))

            ai_service = AIService()
            ai_service.analyze_capsule(capsule.id, db_session)

            assert 'transcriptions' in captured_args
            received_transcriptions = captured_args['transcriptions']
            assert isinstance(received_transcriptions, list)
            assert len(received_transcriptions) == len(transcriptions)
            for t in transcriptions:
                assert t in received_transcriptions


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

    Validates: Requirements 10.5
    """
    with get_db_session() as db_session:
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

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

        p1, p2, p3, p4, p5 = patch_all_ai_services()
        with p1 as mock_ts, p2 as mock_sg, p3 as mock_sd, p4 as mock_va, p5 as mock_rg:
            mock_ts.return_value = Mock()
            mock_sg_inst = Mock()
            mock_sg_inst.generate_summary.return_value = None
            mock_sg.return_value = mock_sg_inst
            mock_sd.return_value = Mock(detect_sentiment=Mock(return_value={"label": "neutral", "confidence": 0.0, "tone_description": ""}))
            mock_va.return_value = Mock(analyze_images=Mock(return_value=[]))
            mock_rg.return_value = Mock(generate_recap=Mock(return_value=None))

            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)

            # With error isolation, analysis still completes even when summary fails
            assert ai_analysis is not None
            assert ai_analysis.capsule_id == capsule.id
            assert ai_analysis.summary is None
            assert ai_analysis.processing_status == "completed"

            stored_analysis = db_session.query(AIAnalysis).filter(
                AIAnalysis.capsule_id == capsule.id
            ).first()
            assert stored_analysis is not None
            assert stored_analysis.summary is None

        db_session.refresh(capsule)
        assert capsule.status == "unlocked"
        assert capsule.text_content == text_content


# Property 39 (Extended): AI service handles exceptions gracefully with error isolation
@settings(max_examples=15, deadline=None)
@given(
    user_id=st.integers(min_value=1, max_value=1000000),
    title=valid_title_strategy(),
    text_content=text_content_strategy()
)
def test_property_39_ai_service_handles_exceptions_gracefully(user_id, title, text_content):
    """
    Property 39 (Extended): AI service handles exceptions gracefully

    With error isolation, individual step failures don't crash the pipeline.
    The analysis still completes with partial results.

    Validates: Requirements 10.5
    """
    with get_db_session() as db_session:
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

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

        p1, p2, p3, p4, p5 = patch_all_ai_services()
        with p1 as mock_ts, p2 as mock_sg, p3 as mock_sd, p4 as mock_va, p5 as mock_rg:
            mock_ts.return_value = Mock()
            # Summary generation raises an exception — error isolation catches it
            mock_sg_inst = Mock()
            mock_sg_inst.generate_summary.side_effect = Exception("API Error")
            mock_sg.return_value = mock_sg_inst
            mock_sd.return_value = Mock(detect_sentiment=Mock(return_value={"label": "neutral", "confidence": 0.0, "tone_description": ""}))
            mock_va.return_value = Mock(analyze_images=Mock(return_value=[]))
            mock_rg.return_value = Mock(generate_recap=Mock(return_value=None))

            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)

            # Error isolation means the pipeline still completes
            assert ai_analysis is not None
            assert ai_analysis.processing_status == "completed"
            assert ai_analysis.summary is None  # summary step failed

        db_session.refresh(capsule)
        assert capsule.status == "unlocked"
        assert capsule.text_content == text_content


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

    Validates: Requirements 10.1
    """
    with get_db_session() as db_session:
        user = User(
            email=f"user{user_id}@example.com",
            password_hash="hashed_password",
            is_verified=True
        )
        db_session.add(user)
        db_session.commit()

        created_at = datetime.now(timezone.utc) - timedelta(days=1)
        unlock_date = datetime.now(timezone.utc) + timedelta(days=30)

        capsule = Capsule(
            user_id=user.id,
            title=title,
            text_content=text_content,
            unlock_date=unlock_date,
            status="locked",
            is_public=False,
            media_urls=[],
            transcriptions=[],
            created_at=created_at
        )
        db_session.add(capsule)
        db_session.commit()
        db_session.refresh(capsule)

        p1, p2, p3, p4, p5 = patch_all_ai_services()
        with p1 as mock_ts, p2 as mock_sg, p3 as mock_sd, p4 as mock_va, p5 as mock_rg:
            mock_ts.return_value = Mock()
            mock_sg_inst = Mock()
            mock_sg_inst.generate_summary.return_value = "This should not be called"
            mock_sg.return_value = mock_sg_inst
            mock_sd.return_value = Mock()
            mock_va.return_value = Mock()
            mock_rg.return_value = Mock()

            ai_service = AIService()
            ai_analysis = ai_service.analyze_capsule(capsule.id, db_session)

            assert ai_analysis is None
            mock_sg_inst.generate_summary.assert_not_called()

            stored_analysis = db_session.query(AIAnalysis).filter(
                AIAnalysis.capsule_id == capsule.id
            ).first()
            assert stored_analysis is None
