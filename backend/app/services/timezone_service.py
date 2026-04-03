"""
Timezone service for handling timezone validation and conversion operations.
Uses Python's zoneinfo module (standard library in Python 3.9+).
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones
from typing import Tuple


class InvalidTimezoneError(Exception):
    """Raised when an invalid IANA timezone identifier is provided"""
    pass


class NonexistentTimeError(Exception):
    """Raised when a local time doesn't exist due to DST spring-forward"""
    pass


class TimezoneService:
    """Handles timezone validation and conversion operations"""
    
    @staticmethod
    def get_available_timezones() -> set[str]:
        """
        Returns set of all valid IANA timezone identifiers.
        Uses Python's zoneinfo.available_timezones().
        """
        return available_timezones()
    
    @staticmethod
    def validate_timezone(timezone: str) -> bool:
        """
        Validates that timezone is a valid IANA identifier.
        
        Args:
            timezone: IANA timezone string (e.g., "America/New_York")
            
        Returns:
            True if valid
            
        Raises:
            InvalidTimezoneError: If timezone is not valid
        """
        if timezone not in available_timezones():
            raise InvalidTimezoneError(
                f"Invalid timezone: '{timezone}'. Please select a valid timezone from the list."
            )
        return True

    @staticmethod
    def convert_to_utc(
        local_datetime: datetime,
        timezone: str,
        dst_ambiguous_strategy: str = "first"
    ) -> datetime:
        """
        Converts a local datetime to UTC using the specified timezone.
        
        Args:
            local_datetime: Naive datetime representing local time
            timezone: IANA timezone identifier
            dst_ambiguous_strategy: How to handle ambiguous times during DST
                                   fall-back ("first" or "second")
        
        Returns:
            UTC datetime with tzinfo=UTC
            
        Raises:
            InvalidTimezoneError: If timezone is invalid
            NonexistentTimeError: If local time doesn't exist (DST gap)
        """
        TimezoneService.validate_timezone(timezone)
        
        tz = ZoneInfo(timezone)
        utc = ZoneInfo("UTC")
        
        # Check if the time is naive (no timezone info)
        if local_datetime.tzinfo is not None:
            local_datetime = local_datetime.replace(tzinfo=None)
        
        # Try to localize the datetime
        try:
            # Create aware datetime in the target timezone
            local_aware = local_datetime.replace(tzinfo=tz)
            
            # Check for DST gap (nonexistent time)
            # Convert to UTC and back to check if time is preserved
            utc_dt = local_aware.astimezone(utc)
            back_to_local = utc_dt.astimezone(tz)
            
            # If the hour changed, we hit a DST gap
            if back_to_local.replace(tzinfo=None) != local_datetime:
                # Check if this is a gap (spring forward) vs fold (fall back)
                # For gaps, the time doesn't exist
                # Try one hour before and after to detect gap
                hour_before = (local_datetime - timedelta(hours=1)).replace(tzinfo=tz)
                hour_after = (local_datetime + timedelta(hours=1)).replace(tzinfo=tz)
                
                # If UTC offsets differ by more than 1 hour, it's a DST transition
                offset_before = hour_before.utcoffset()
                offset_after = hour_after.utcoffset()
                
                if offset_after > offset_before:
                    # Spring forward - time doesn't exist
                    raise NonexistentTimeError(
                        f"The time {local_datetime.strftime('%Y-%m-%d %H:%M')} does not exist "
                        f"in {timezone} due to daylight saving time."
                    )
            
            # Handle ambiguous times (DST fall-back)
            # fold=0 means first occurrence, fold=1 means second
            fold = 0 if dst_ambiguous_strategy == "first" else 1
            local_aware = local_datetime.replace(tzinfo=tz, fold=fold)
            
            return local_aware.astimezone(utc)
            
        except Exception as e:
            if isinstance(e, (InvalidTimezoneError, NonexistentTimeError)):
                raise
            raise InvalidTimezoneError(f"Error converting datetime: {str(e)}")

    @staticmethod
    def convert_from_utc(utc_datetime: datetime, timezone: str) -> datetime:
        """
        Converts a UTC datetime to the specified timezone.
        
        Args:
            utc_datetime: Datetime in UTC
            timezone: IANA timezone identifier
            
        Returns:
            Datetime in the specified timezone
            
        Raises:
            InvalidTimezoneError: If timezone is invalid
        """
        TimezoneService.validate_timezone(timezone)
        
        tz = ZoneInfo(timezone)
        utc = ZoneInfo("UTC")
        
        # Ensure the datetime has UTC timezone
        if utc_datetime.tzinfo is None:
            utc_datetime = utc_datetime.replace(tzinfo=utc)
        elif utc_datetime.tzinfo != utc:
            utc_datetime = utc_datetime.astimezone(utc)
        
        return utc_datetime.astimezone(tz)
    
    @staticmethod
    def get_timezone_abbreviation(dt: datetime, timezone: str) -> str:
        """
        Returns the timezone abbreviation for a given datetime.
        
        Args:
            dt: Datetime to get abbreviation for
            timezone: IANA timezone identifier
            
        Returns:
            Abbreviation string (e.g., "EST", "PST", "UTC")
        """
        TimezoneService.validate_timezone(timezone)
        
        tz = ZoneInfo(timezone)
        
        # If datetime is naive, localize it
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.astimezone(tz)
        
        # Get the timezone abbreviation using strftime
        return dt.strftime("%Z")
    
    @staticmethod
    def adjust_nonexistent_time(
        local_datetime: datetime,
        timezone: str
    ) -> Tuple[datetime, bool]:
        """
        Adjusts a nonexistent local time (DST gap) to the next valid time.
        
        Args:
            local_datetime: Naive datetime that may not exist
            timezone: IANA timezone identifier
            
        Returns:
            Tuple of (adjusted_datetime, was_adjusted)
        """
        TimezoneService.validate_timezone(timezone)
        
        tz = ZoneInfo(timezone)
        utc = ZoneInfo("UTC")
        
        if local_datetime.tzinfo is not None:
            local_datetime = local_datetime.replace(tzinfo=None)
        
        # Create aware datetime
        local_aware = local_datetime.replace(tzinfo=tz)
        
        # Convert to UTC and back to detect if time exists
        utc_dt = local_aware.astimezone(utc)
        back_to_local = utc_dt.astimezone(tz)
        back_naive = back_to_local.replace(tzinfo=None)
        
        if back_naive != local_datetime:
            # Time was adjusted - check if it's a gap (spring forward)
            hour_before = (local_datetime - timedelta(hours=1)).replace(tzinfo=tz)
            hour_after = (local_datetime + timedelta(hours=1)).replace(tzinfo=tz)
            
            offset_before = hour_before.utcoffset()
            offset_after = hour_after.utcoffset()
            
            if offset_after > offset_before:
                # Spring forward gap - return the adjusted time
                return back_naive, True
        
        # Time exists as-is
        return local_datetime, False
