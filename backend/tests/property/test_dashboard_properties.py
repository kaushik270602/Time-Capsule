# Feature: timelock
# Property-based tests for capsule dashboard, filtering, search, sorting, and public feed

import pytest
from hypothesis import given, strategies as st, settings
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.user import User
from app.models.capsule import Capsule
from app.services.capsule_service import CapsuleService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_db_session():
    """Create a fresh in-memory database session for testing.

    Attaches a mapper-level ``load`` listener on the Capsule model so that
    every time a Capsule row is materialised from SQLite the naive datetime
    columns get UTC tzinfo re-attached (SQLite strips timezone info).
    """
    from sqlalchemy import event
    from app.models.capsule import Capsule as CapsuleModel

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=True)
    session = Session()

    # Ensure every Capsule loaded from SQLite gets UTC tzinfo on datetime cols
    @event.listens_for(CapsuleModel, "load")
    def _attach_utc(target, context):
        for attr in ("unlock_date", "created_at", "updated_at"):
            val = getattr(target, attr, None)
            if isinstance(val, datetime) and val.tzinfo is None:
                object.__setattr__(target, attr, val.replace(tzinfo=timezone.utc))

    @event.listens_for(CapsuleModel, "refresh")
    def _attach_utc_refresh(target, context, attrs):
        for attr in ("unlock_date", "created_at", "updated_at"):
            val = getattr(target, attr, None)
            if isinstance(val, datetime) and val.tzinfo is None:
                object.__setattr__(target, attr, val.replace(tzinfo=timezone.utc))

    try:
        yield session
    finally:
        event.remove(CapsuleModel, "load", _attach_utc)
        event.remove(CapsuleModel, "refresh", _attach_utc_refresh)
        session.close()


def _create_user(session, user_id=1):
    """Insert a user and return it."""
    user = User(
        email=f"user{user_id}@example.com",
        password_hash="hashed_password",
        is_verified=True,
    )
    session.add(user)
    session.commit()
    return user


def _create_capsule(session, user, *, title="Cap", text_content="text",
                     status="locked", is_public=False, unlock_offset_days=30):
    """Insert a capsule with sensible defaults and return it."""
    capsule = Capsule(
        user_id=user.id,
        title=title,
        text_content=text_content,
        unlock_date=datetime.now(timezone.utc) + timedelta(days=unlock_offset_days),
        status=status,
        is_public=is_public,
        media_urls=[],
        transcriptions=[],
    )
    session.add(capsule)
    session.commit()
    session.refresh(capsule)
    return capsule


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def valid_title_strategy():
    return st.text(min_size=1, max_size=100).filter(lambda t: t.strip() != "")


def capsule_spec_strategy():
    """Generate a specification dict for a single capsule."""
    return st.fixed_dictionaries({
        "title": valid_title_strategy(),
        "text_content": st.one_of(st.none(), st.text(min_size=1, max_size=200)),
        "status": st.sampled_from(["locked", "unlocked"]),
        "is_public": st.booleans(),
        "unlock_offset_days": st.integers(min_value=1, max_value=365),
    })


# ---------------------------------------------------------------------------
# Property 30: Dashboard displays all user capsules
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    capsule_specs=st.lists(capsule_spec_strategy(), min_size=0, max_size=8),
)
def test_property_30_dashboard_displays_all_user_capsules(capsule_specs):
    """
    Property 30: Dashboard displays all user capsules

    For any user accessing their dashboard, the system should return all
    capsules owned by that user, separated into locked and unlocked sections.

    **Validates: Requirements 8.1, 8.2**
    """
    with get_db_session() as db:
        user = _create_user(db, user_id=1)
        # Also create a second user with capsules that should NOT appear
        other_user = _create_user(db, user_id=2)
        _create_capsule(db, other_user, title="Other user capsule")

        # Create capsules for the target user
        created_ids = set()
        expected_locked = 0
        expected_unlocked = 0
        for spec in capsule_specs:
            c = _create_capsule(
                db, user,
                title=spec["title"],
                text_content=spec["text_content"],
                status=spec["status"],
                is_public=spec["is_public"],
                unlock_offset_days=spec["unlock_offset_days"],
            )
            created_ids.add(c.id)
            if spec["status"] == "locked":
                expected_locked += 1
            else:
                expected_unlocked += 1

        svc = CapsuleService(db)
        results = svc.list_user_capsules(user_id=user.id)

        # All user capsules are returned
        returned_ids = {r["id"] for r in results}
        assert returned_ids == created_ids, (
            "Dashboard must return exactly the user's capsules"
        )

        # Locked and unlocked are distinguishable
        locked_results = [r for r in results if r["status"] == "locked"]
        unlocked_results = [r for r in results if r["status"] == "unlocked"]
        assert len(locked_results) == expected_locked
        assert len(unlocked_results) == expected_unlocked


# ---------------------------------------------------------------------------
# Property 31: Dashboard statistics are accurate
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    capsule_specs=st.lists(capsule_spec_strategy(), min_size=0, max_size=8),
)
def test_property_31_dashboard_statistics_are_accurate(capsule_specs):
    """
    Property 31: Dashboard statistics are accurate

    For any user's dashboard, the displayed statistics (total capsules,
    locked count, unlocked count) should match the actual counts in the
    database.

    **Validates: Requirements 8.8**
    """
    with get_db_session() as db:
        user = _create_user(db)

        expected_total = len(capsule_specs)
        expected_locked = sum(1 for s in capsule_specs if s["status"] == "locked")
        expected_unlocked = expected_total - expected_locked

        for spec in capsule_specs:
            _create_capsule(
                db, user,
                title=spec["title"],
                text_content=spec["text_content"],
                status=spec["status"],
                is_public=spec["is_public"],
                unlock_offset_days=spec["unlock_offset_days"],
            )

        svc = CapsuleService(db)
        results = svc.list_user_capsules(user_id=user.id)

        total = len(results)
        locked_count = sum(1 for r in results if r["status"] == "locked")
        unlocked_count = sum(1 for r in results if r["status"] == "unlocked")

        assert total == expected_total, "Total capsule count must match"
        assert locked_count == expected_locked, "Locked count must match"
        assert unlocked_count == expected_unlocked, "Unlocked count must match"


# ---------------------------------------------------------------------------
# Property 32: Capsule filters work correctly
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    capsule_specs=st.lists(capsule_spec_strategy(), min_size=1, max_size=8),
    filter_status=st.sampled_from(["locked", "unlocked"]),
)
def test_property_32_capsule_filters_work_correctly(capsule_specs, filter_status):
    """
    Property 32: Capsule filters work correctly

    For any filter applied to the capsule list (by status), only capsules
    matching the filter criteria should be returned.

    **Validates: Requirements 8.5**
    """
    with get_db_session() as db:
        user = _create_user(db)

        for spec in capsule_specs:
            _create_capsule(
                db, user,
                title=spec["title"],
                text_content=spec["text_content"],
                status=spec["status"],
                is_public=spec["is_public"],
                unlock_offset_days=spec["unlock_offset_days"],
            )

        svc = CapsuleService(db)
        results = svc.list_user_capsules(user_id=user.id, filter_status=filter_status)

        # Every returned capsule must match the filter
        for r in results:
            assert r["status"] == filter_status, (
                f"Filtered results must only contain '{filter_status}' capsules"
            )

        # Count should match expected
        expected_count = sum(
            1 for s in capsule_specs if s["status"] == filter_status
        )
        assert len(results) == expected_count, (
            f"Filter should return exactly {expected_count} capsules"
        )


# ---------------------------------------------------------------------------
# Property 33: Capsule search includes all text content
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    search_term=st.text(
        alphabet=st.characters(whitelist_categories=("L",)),
        min_size=3, max_size=10,
    ),
)
def test_property_33_capsule_search_includes_all_text_content(search_term):
    """
    Property 33: Capsule search includes all text content

    For any search query, the system should return capsules where the query
    matches the title or text content.

    **Validates: Requirements 8.6, 11.4**
    """
    with get_db_session() as db:
        user = _create_user(db)

        # Capsule with search term in title only
        c_title = _create_capsule(
            db, user,
            title=f"My {search_term} capsule",
            text_content="unrelated body",
            status="unlocked",
        )
        # Capsule with search term in text_content only
        c_body = _create_capsule(
            db, user,
            title="Unrelated title",
            text_content=f"Some {search_term} content here",
            status="locked",
        )
        # Capsule with no match
        _create_capsule(
            db, user,
            title="Nothing here",
            text_content="Nothing here either",
            status="locked",
        )

        svc = CapsuleService(db)
        results = svc.list_user_capsules(user_id=user.id, search_query=search_term)
        result_ids = {r["id"] for r in results}

        assert c_title.id in result_ids, (
            "Search should find capsules matching in title"
        )
        assert c_body.id in result_ids, (
            "Search should find capsules matching in text_content"
        )


# ---------------------------------------------------------------------------
# Property 34: Capsules are sorted by unlock date
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    offsets=st.lists(
        st.integers(min_value=1, max_value=3650),
        min_size=2,
        max_size=8,
    ),
)
def test_property_34_capsules_sorted_by_unlock_date(offsets):
    """
    Property 34: Capsules are sorted by unlock date

    For any capsule list request without explicit sorting, capsules should
    be sorted by unlock_date with nearest dates first.

    **Validates: Requirements 8.7**
    """
    with get_db_session() as db:
        user = _create_user(db)

        for offset in offsets:
            _create_capsule(db, user, unlock_offset_days=offset)

        svc = CapsuleService(db)
        results = svc.list_user_capsules(user_id=user.id)

        unlock_dates = [r["unlock_date"] for r in results]
        # Normalise to naive for comparison (SQLite strips tz)
        normalised = []
        for d in unlock_dates:
            normalised.append(d.replace(tzinfo=None) if d.tzinfo else d)

        assert normalised == sorted(normalised), (
            "Capsules must be sorted by unlock_date ascending (nearest first)"
        )


# ---------------------------------------------------------------------------
# Property 35: Public feed shows recent unlocked public capsules
# ---------------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(
    capsule_specs=st.lists(capsule_spec_strategy(), min_size=1, max_size=8),
)
def test_property_35_public_feed_shows_recent_unlocked_public_capsules(capsule_specs):
    """
    Property 35: Public feed shows recent unlocked public capsules

    For any public feed request, the system should return only capsules where
    is_public=True AND status="unlocked", sorted by unlock_date descending,
    with required fields (title, creator/user_id, unlock_date, preview).

    **Validates: Requirements 9.4, 9.5**
    """
    with get_db_session() as db:
        user = _create_user(db)

        expected_feed_ids = set()
        for spec in capsule_specs:
            c = _create_capsule(
                db, user,
                title=spec["title"],
                text_content=spec["text_content"],
                status=spec["status"],
                is_public=spec["is_public"],
                unlock_offset_days=spec["unlock_offset_days"],
            )
            if spec["is_public"] and spec["status"] == "unlocked":
                expected_feed_ids.add(c.id)

        svc = CapsuleService(db)
        feed = svc.get_public_feed()

        feed_ids = {c["id"] for c in feed}
        assert feed_ids == expected_feed_ids, (
            "Public feed must contain exactly the unlocked public capsules"
        )

        # Verify required fields present
        for item in feed:
            assert "title" in item, "Public feed item must include title"
            assert "user_id" in item, "Public feed item must include creator (user_id)"
            assert "unlock_date" in item, "Public feed item must include unlock_date"
            assert "text_content" in item, "Public feed item must include preview content"

        # Verify descending unlock_date order
        if len(feed) >= 2:
            dates = [f["unlock_date"] for f in feed]
            normalised = [d.replace(tzinfo=None) if d.tzinfo else d for d in dates]
            assert normalised == sorted(normalised, reverse=True), (
                "Public feed must be sorted by unlock_date descending"
            )
