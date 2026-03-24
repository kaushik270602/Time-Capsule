# Feature: timelock
# Property-based tests for access control and locking mechanism

import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timezone, timedelta
from app.services.locking_mechanism import LockingMechanism, AccessDeniedError
from app.models.capsule import Capsule


# Strategy for generating capsule-like objects
@st.composite
def capsule_strategy(draw, locked=None, is_public=None, owner_id=None):
    """Generate capsule objects with various states"""
    user_id = owner_id if owner_id is not None else draw(st.integers(min_value=1, max_value=1000))
    title = draw(st.text(min_size=1, max_size=255))
    text_content = draw(st.one_of(st.none(), st.text(max_size=1000)))
    
    # Generate unlock date
    if locked is None:
        # Random locked/unlocked state
        is_locked = draw(st.booleans())
    else:
        is_locked = locked
    
    if is_locked:
        # Future date for locked capsules
        unlock_date = datetime.now(timezone.utc) + timedelta(
            days=draw(st.integers(min_value=1, max_value=365))
        )
        status = "locked"
    else:
        # Past date for unlocked capsules
        unlock_date = datetime.now(timezone.utc) - timedelta(
            days=draw(st.integers(min_value=1, max_value=365))
        )
        status = "unlocked"
    
    public = is_public if is_public is not None else draw(st.booleans())
    
    # Create a mock capsule object
    capsule = type('Capsule', (), {
        'id': draw(st.integers(min_value=1, max_value=10000)),
        'user_id': user_id,
        'title': title,
        'text_content': text_content,
        'media_urls': [],
        'transcriptions': [],
        'unlock_date': unlock_date,
        'status': status,
        'is_public': public,
        'created_at': datetime.now(timezone.utc) - timedelta(days=draw(st.integers(min_value=1, max_value=730))),
        'updated_at': datetime.now(timezone.utc)
    })()
    
    return capsule


# Property 15: Locked capsule content is inaccessible
@settings(max_examples=100)
@given(capsule=capsule_strategy(locked=True))
def test_property_15_locked_capsule_content_inaccessible(capsule):
    """
    Property 15: Locked capsule content is inaccessible
    
    For any capsule with Content_Status "locked" or where current time is before unlock_date,
    attempting to access the capsule content should be denied with an error,
    returning only metadata (title, unlock_date, status).
    
    Validates: Requirements 5.2, 5.4, 5.6
    """
    # Verify capsule is locked
    assert LockingMechanism.is_locked(capsule) == True
    
    # Owner should get metadata only, not content
    result = LockingMechanism.get_content_or_deny(capsule, capsule.user_id)
    
    # Verify metadata is returned
    assert result['id'] == capsule.id
    assert result['title'] == capsule.title
    assert result['unlock_date'] == capsule.unlock_date
    assert result['status'] == capsule.status
    
    # Verify content is NOT returned
    assert result['text_content'] is None
    assert result['media_urls'] == []
    assert result['transcriptions'] == []
    
    # Non-owner should be denied access completely
    other_user_id = capsule.user_id + 1
    with pytest.raises(AccessDeniedError, match="Cannot access locked capsule"):
        LockingMechanism.get_content_or_deny(capsule, other_user_id)


# Property 16: Locked capsules are immutable
@settings(max_examples=100)
@given(capsule=capsule_strategy(locked=True))
def test_property_16_locked_capsules_immutable(capsule):
    """
    Property 16: Locked capsules are immutable
    
    For any capsule with Content_Status "locked", attempting to modify or delete
    the capsule content should be rejected with an error.
    
    Note: This property tests the locking mechanism's access control.
    The actual immutability enforcement would be in the CapsuleService layer.
    Here we verify that locked capsules cannot have their content accessed for modification.
    
    Validates: Requirements 5.3
    """
    # Verify capsule is locked
    assert LockingMechanism.is_locked(capsule) == True
    
    # Verify that content access is denied (prerequisite for modification)
    # Even the owner cannot access content for modification when locked
    assert LockingMechanism.can_access_content(capsule, capsule.user_id) == False
    
    # Non-owner also cannot access
    other_user_id = capsule.user_id + 1
    assert LockingMechanism.can_access_content(capsule, other_user_id) == False


# Property 18: Private capsules are owner-only
@settings(max_examples=100)
@given(
    capsule=capsule_strategy(locked=False, is_public=False),
    other_user_id=st.integers(min_value=1, max_value=1000)
)
def test_property_18_private_capsules_owner_only(capsule, other_user_id):
    """
    Property 18: Private capsules are owner-only
    
    For any private capsule (is_public = false), only the capsule owner should be able
    to access the capsule, regardless of lock status.
    
    Validates: Requirements 5.6, 15.8
    """
    # Ensure other_user_id is different from owner
    if other_user_id == capsule.user_id:
        other_user_id = capsule.user_id + 1
    
    # Verify capsule is unlocked and private
    assert LockingMechanism.is_locked(capsule) == False
    assert capsule.is_public == False
    
    # Owner should have access
    assert LockingMechanism.can_access_content(capsule, capsule.user_id) == True
    
    # Owner should get full content
    result = LockingMechanism.get_content_or_deny(capsule, capsule.user_id)
    assert result['text_content'] == capsule.text_content
    assert result['media_urls'] == capsule.media_urls
    
    # Non-owner should NOT have access
    assert LockingMechanism.can_access_content(capsule, other_user_id) == False
    
    # Non-owner should be denied with error
    with pytest.raises(AccessDeniedError, match="Access denied"):
        LockingMechanism.get_content_or_deny(capsule, other_user_id)
    
    # Unauthenticated user (None) should also be denied
    assert LockingMechanism.can_access_content(capsule, None) == False
    
    with pytest.raises(AccessDeniedError, match="Access denied"):
        LockingMechanism.get_content_or_deny(capsule, None)


# Additional test: Public unlocked capsules are accessible to all
@settings(max_examples=100)
@given(
    capsule=capsule_strategy(locked=False, is_public=True),
    random_user_id=st.one_of(st.none(), st.integers(min_value=1, max_value=1000))
)
def test_public_unlocked_capsules_accessible_to_all(capsule, random_user_id):
    """
    Verify that public unlocked capsules are accessible to any user,
    including unauthenticated users.
    
    This complements Property 18 by testing the opposite case.
    """
    # Verify capsule is unlocked and public
    assert LockingMechanism.is_locked(capsule) == False
    assert capsule.is_public == True
    
    # Any user (including None) should have access
    assert LockingMechanism.can_access_content(capsule, random_user_id) == True
    
    # Any user should get full content
    result = LockingMechanism.get_content_or_deny(capsule, random_user_id)
    assert result['text_content'] == capsule.text_content
    assert result['media_urls'] == capsule.media_urls
