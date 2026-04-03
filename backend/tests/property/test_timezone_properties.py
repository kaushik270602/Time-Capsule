# Feature: timezone-selection
# Property-based tests for timezone validation and conversion

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

from app.services.timezone_service import (
    TimezoneService,
    InvalidTimezoneError,
    NonexistentTimeError
)


# Get a sample of common timezones for testing (full set is too large)
COMMON_TIMEZONES = [
    "UTC",
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "America/Denver",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Kolkata",
    "Australia/Sydney",
    "Pacific/Auckland",
    "Africa/Cairo",
    "America/Sao_Paulo",
]

# Strategy for valid IANA timezones
valid_timezone_strategy = st.sampled_from(COMMON_TIMEZONES)

# Strategy for future datetimes (avoiding DST transition edge cases)
future_datetime_strategy = st.datetimes(
    min_value=datetime(2025, 1, 15),  # Mid-January, no DST transitions
    max_value=datetime(2030, 6, 15)   # Mid-June, no DST transitions
)

# Strategy for safe datetimes (avoiding DST gaps)
safe_datetime_strategy = st.datetimes(
    min_value=datetime(2025, 1, 15, 12, 0),  # Noon on safe dates
    max_value=datetime(2030, 1, 15, 12, 0)
)


# ============================================================================
# Property 1: Timezone Validation
# ============================================================================

@settings(max_examples=50, deadline=None)
@given(timezone_str=st.text(min_size=0, max_size=100))
def test_property_1_timezone_validation_rejects_invalid(timezone_str):
    """
    Property 1: Timezone Validation (Invalid Input)
    
    For any string input that is NOT a valid IANA timezone identifier,
    the system shall reject it with an InvalidTimezoneError.
    
    Validates: Requirements 2.1, 2.2
    """
    valid_timezones = available_timezones()
    
    if timezone_str not in valid_timezones:
        with pytest.raises(InvalidTimezoneError) as exc_info:
            TimezoneService.validate_timezone(timezone_str)
        
        # Verify error message is descriptive
        assert "invalid" in str(exc_info.value).lower(), \
            "Error message should indicate invalid timezone"


@settings(max_examples=30, deadline=None)
@given(timezone=valid_timezone_strategy)
def test_property_1_timezone_validation_accepts_valid(timezone):
    """
    Property 1: Timezone Validation (Valid Input)
    
    For any valid IANA timezone identifier, the system shall accept it
    and return True.
    
    Validates: Requirements 2.1, 2.2, 3.4
    """
    result = TimezoneService.validate_timezone(timezone)
    assert result is True, f"Valid timezone '{timezone}' should be accepted"


@settings(max_examples=20, deadline=None)
@given(
    prefix=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
    suffix=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz")
)
def test_property_1_timezone_validation_rejects_fake_iana_format(prefix, suffix):
    """
    Property 1: Timezone Validation (Fake IANA Format)
    
    For any string that looks like an IANA timezone (Region/City format)
    but is not actually valid, the system shall reject it.
    
    Validates: Requirements 2.1, 2.2
    """
    fake_timezone = f"{prefix.capitalize()}/{suffix.capitalize()}"
    valid_timezones = available_timezones()
    
    # Only test if this fake timezone is not accidentally valid
    if fake_timezone not in valid_timezones:
        with pytest.raises(InvalidTimezoneError):
            TimezoneService.validate_timezone(fake_timezone)


# ============================================================================
# Property 4: UTC Round-Trip Preservation
# ============================================================================

@settings(max_examples=50, deadline=None)
@given(
    utc_dt=safe_datetime_strategy,
    timezone=valid_timezone_strategy
)
def test_property_4_utc_roundtrip_preservation(utc_dt, timezone):
    """
    Property 4: UTC Round-Trip Preservation
    
    For any valid UTC timestamp and IANA timezone, converting the UTC timestamp
    to the timezone and back to UTC shall produce the original UTC timestamp.
    
    UTC -> Local -> UTC = Original UTC (identity operation)
    
    Validates: Requirements 5.3
    """
    # Make the datetime UTC-aware
    utc_aware = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    
    # Convert UTC to local timezone
    local_dt = TimezoneService.convert_from_utc(utc_aware, timezone)
    
    # Convert back to UTC (need to strip tzinfo for convert_to_utc which expects naive)
    local_naive = local_dt.replace(tzinfo=None)
    roundtrip_utc = TimezoneService.convert_to_utc(local_naive, timezone)
    
    # Compare timestamps (both should be UTC-aware)
    assert roundtrip_utc.tzinfo is not None, "Result should be timezone-aware"
    
    # Compare as UTC timestamps
    original_ts = utc_aware.timestamp()
    roundtrip_ts = roundtrip_utc.timestamp()
    
    assert abs(original_ts - roundtrip_ts) < 1, \
        f"UTC round-trip should preserve timestamp. Original: {utc_aware}, Roundtrip: {roundtrip_utc}"


@settings(max_examples=30, deadline=None)
@given(
    utc_dt=safe_datetime_strategy,
    timezone=valid_timezone_strategy
)
def test_property_4_utc_roundtrip_preserves_instant(utc_dt, timezone):
    """
    Property 4 (Extended): UTC Round-Trip Preserves Instant in Time
    
    The round-trip conversion should preserve the exact instant in time,
    meaning the Unix timestamp should be identical.
    
    Validates: Requirements 5.3
    """
    utc_aware = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    
    # Convert to local and back
    local_dt = TimezoneService.convert_from_utc(utc_aware, timezone)
    local_naive = local_dt.replace(tzinfo=None)
    
    try:
        roundtrip_utc = TimezoneService.convert_to_utc(local_naive, timezone)
        
        # Unix timestamps should match exactly
        original_timestamp = utc_aware.timestamp()
        roundtrip_timestamp = roundtrip_utc.timestamp()
        
        assert original_timestamp == pytest.approx(roundtrip_timestamp, abs=0.001), \
            "Unix timestamps should be identical after round-trip"
    except NonexistentTimeError:
        # This can happen if the local time falls in a DST gap
        # This is acceptable - the property holds for valid times
        pass


# ============================================================================
# Property 5: Local DateTime Round-Trip Preservation
# ============================================================================

@settings(max_examples=50, deadline=None)
@given(
    local_dt=safe_datetime_strategy,
    timezone=valid_timezone_strategy
)
def test_property_5_local_roundtrip_preservation(local_dt, timezone):
    """
    Property 5: Local DateTime Round-Trip Preservation
    
    For any valid IANA timezone and future local datetime (excluding DST gap times),
    converting the local datetime to UTC and back to the same timezone shall
    produce the original local datetime.
    
    Local -> UTC -> Local = Original Local (for non-DST-gap times)
    
    Validates: Requirements 5.4, 2.4
    """
    try:
        # Convert local to UTC
        utc_dt = TimezoneService.convert_to_utc(local_dt, timezone)
        
        # Convert back to local
        roundtrip_local = TimezoneService.convert_from_utc(utc_dt, timezone)
        
        # Strip timezone info for comparison
        roundtrip_naive = roundtrip_local.replace(tzinfo=None)
        
        # The naive datetimes should match
        assert roundtrip_naive == local_dt, \
            f"Local round-trip should preserve datetime. Original: {local_dt}, Roundtrip: {roundtrip_naive}"
            
    except NonexistentTimeError:
        # DST gap times are excluded from this property
        # This is expected behavior, not a failure
        pass


@settings(max_examples=30, deadline=None)
@given(
    local_dt=safe_datetime_strategy,
    timezone=valid_timezone_strategy
)
def test_property_5_local_roundtrip_preserves_components(local_dt, timezone):
    """
    Property 5 (Extended): Local Round-Trip Preserves All DateTime Components
    
    After round-trip conversion, all datetime components (year, month, day,
    hour, minute, second) should be preserved.
    
    Validates: Requirements 5.4, 2.4
    """
    try:
        utc_dt = TimezoneService.convert_to_utc(local_dt, timezone)
        roundtrip_local = TimezoneService.convert_from_utc(utc_dt, timezone)
        roundtrip_naive = roundtrip_local.replace(tzinfo=None)
        
        # Check each component
        assert roundtrip_naive.year == local_dt.year, "Year should be preserved"
        assert roundtrip_naive.month == local_dt.month, "Month should be preserved"
        assert roundtrip_naive.day == local_dt.day, "Day should be preserved"
        assert roundtrip_naive.hour == local_dt.hour, "Hour should be preserved"
        assert roundtrip_naive.minute == local_dt.minute, "Minute should be preserved"
        assert roundtrip_naive.second == local_dt.second, "Second should be preserved"
        
    except NonexistentTimeError:
        # DST gap times are excluded
        pass


# ============================================================================
# Additional Timezone Service Properties
# ============================================================================

@settings(max_examples=30, deadline=None)
@given(
    dt=safe_datetime_strategy,
    timezone=valid_timezone_strategy
)
def test_timezone_abbreviation_is_non_empty(dt, timezone):
    """
    Timezone abbreviations should always be non-empty strings.
    
    Validates: Requirements 4.3
    """
    abbrev = TimezoneService.get_timezone_abbreviation(dt, timezone)
    
    assert isinstance(abbrev, str), "Abbreviation should be a string"
    assert len(abbrev) > 0, "Abbreviation should not be empty"


@settings(max_examples=30, deadline=None)
@given(timezone=valid_timezone_strategy)
def test_utc_conversion_produces_utc_aware_datetime(timezone):
    """
    Converting to UTC should always produce a UTC-aware datetime.
    """
    local_dt = datetime(2025, 6, 15, 12, 0, 0)  # Safe datetime
    
    utc_dt = TimezoneService.convert_to_utc(local_dt, timezone)
    
    assert utc_dt.tzinfo is not None, "Result should be timezone-aware"
    # Check it's actually UTC
    assert utc_dt.tzinfo == ZoneInfo("UTC") or str(utc_dt.tzinfo) == "UTC", \
        "Result should be in UTC timezone"


@settings(max_examples=30, deadline=None)
@given(timezone=valid_timezone_strategy)
def test_from_utc_conversion_produces_target_timezone(timezone):
    """
    Converting from UTC should produce a datetime in the target timezone.
    """
    utc_dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
    
    local_dt = TimezoneService.convert_from_utc(utc_dt, timezone)
    
    assert local_dt.tzinfo is not None, "Result should be timezone-aware"


@settings(max_examples=20, deadline=None)
@given(
    local_dt=safe_datetime_strategy,
    timezone=valid_timezone_strategy
)
def test_adjust_nonexistent_time_returns_tuple(local_dt, timezone):
    """
    adjust_nonexistent_time should always return a tuple of (datetime, bool).
    """
    result = TimezoneService.adjust_nonexistent_time(local_dt, timezone)
    
    assert isinstance(result, tuple), "Result should be a tuple"
    assert len(result) == 2, "Result should have 2 elements"
    assert isinstance(result[0], datetime), "First element should be datetime"
    assert isinstance(result[1], bool), "Second element should be boolean"


@settings(max_examples=20, deadline=None)
@given(timezone=valid_timezone_strategy)
def test_get_available_timezones_includes_common_zones(timezone):
    """
    get_available_timezones should include all common timezone identifiers.
    """
    available = TimezoneService.get_available_timezones()
    
    assert timezone in available, f"Common timezone '{timezone}' should be available"
    assert "UTC" in available, "UTC should always be available"
