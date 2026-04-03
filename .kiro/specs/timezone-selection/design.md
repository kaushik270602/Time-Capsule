# Design Document: Timezone Selection for Capsule Unlock Dates

## Overview

This feature adds timezone awareness to the TimeLock capsule creation and display workflow. Users will be able to select a timezone when setting an unlock date, ensuring capsules unlock at the intended local time. The system will store the selected timezone alongside the UTC timestamp, enabling accurate display of unlock dates in the user's original timezone context.

The implementation spans both frontend (timezone selector component, display formatting) and backend (timezone validation, conversion, storage). The backend will use Python's `zoneinfo` module (standard library in Python 3.9+) for IANA timezone handling, while the frontend will use the browser's `Intl` API for timezone detection and `date-fns-tz` for timezone-aware formatting.

## Architecture

### Component Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  CapsuleForm                                              │  │
│  │  ├── TimezoneSelector (new)                               │  │
│  │  │   ├── Searchable dropdown of IANA timezones            │  │
│  │  │   └── Auto-detect browser timezone via Intl API        │  │
│  │  └── Unlock date input (existing)                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  UnlockDisplay (new utility)                              │  │
│  │  ├── Convert UTC to stored timezone                       │  │
│  │  └── Format with timezone abbreviation                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │ POST /capsules { timezone: "America/New_York" }
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  CapsuleRouter                                            │  │
│  │  └── Accept timezone field in create/update requests      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  TimezoneService (new)                                    │  │
│  │  ├── validate_timezone(tz: str) -> bool                   │  │
│  │  ├── convert_to_utc(dt, tz) -> datetime                   │  │
│  │  ├── convert_from_utc(dt, tz) -> datetime                 │  │
│  │  └── Handle DST transitions                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  CapsuleService (modified)                                │  │
│  │  └── Store timezone with capsule                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database (PostgreSQL)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  capsules table                                           │  │
│  │  ├── unlock_date TIMESTAMP (UTC) - existing               │  │
│  │  └── timezone VARCHAR(64) - new column                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow: Capsule Creation

```
User selects:                    Frontend sends:              Backend processes:
┌─────────────────┐             ┌─────────────────┐          ┌─────────────────┐
│ Date: 2024-12-25│             │ unlock_date:    │          │ 1. Validate tz  │
│ Time: 09:00     │ ──────────► │   "2024-12-25   │ ───────► │ 2. Convert to   │
│ TZ: America/    │             │    T09:00:00"   │          │    UTC          │
│     New_York    │             │ timezone:       │          │ 3. Store both   │
└─────────────────┘             │   "America/     │          └─────────────────┘
                                │    New_York"    │                   │
                                └─────────────────┘                   ▼
                                                             ┌─────────────────┐
                                                             │ DB stores:      │
                                                             │ unlock_date:    │
                                                             │  2024-12-25     │
                                                             │  14:00:00 UTC   │
                                                             │ timezone:       │
                                                             │  America/       │
                                                             │  New_York       │
                                                             └─────────────────┘
```

### Data Flow: Capsule Display

```
Database returns:               Backend sends:               Frontend displays:
┌─────────────────┐             ┌─────────────────┐          ┌─────────────────┐
│ unlock_date:    │             │ unlock_date:    │          │ "Dec 25, 2024   │
│  2024-12-25     │ ──────────► │   "2024-12-25   │ ───────► │  9:00 AM EST"   │
│  14:00:00 UTC   │             │    T14:00:00Z"  │          │                 │
│ timezone:       │             │ timezone:       │          │                 │
│  America/       │             │   "America/     │          │                 │
│  New_York       │             │    New_York"    │          │                 │
└─────────────────┘             └─────────────────┘          └─────────────────┘
```

## Components and Interfaces

### 1. TimezoneService (Backend)

**Location:** `backend/app/services/timezone_service.py`

```python
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones
from typing import Optional

class InvalidTimezoneError(Exception):
    """Raised when an invalid IANA timezone identifier is provided"""
    pass

class AmbiguousTimeError(Exception):
    """Raised when a local time is ambiguous due to DST fall-back"""
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
    
    @staticmethod
    def adjust_nonexistent_time(
        local_datetime: datetime,
        timezone: str
    ) -> tuple[datetime, bool]:
        """
        Adjusts a nonexistent local time (DST gap) to the next valid time.
        
        Args:
            local_datetime: Naive datetime that may not exist
            timezone: IANA timezone identifier
            
        Returns:
            Tuple of (adjusted_datetime, was_adjusted)
        """
```

### 2. CapsuleService (Modified)

**Location:** `backend/app/services/capsule_service.py`

```python
class CapsuleService:
    def create_capsule(
        self,
        user_id: int,
        title: str,
        text_content: Optional[str],
        unlock_date: datetime,
        timezone: str = "UTC",  # New parameter
        is_public: bool = False,
        media_urls: List[str] = None
    ) -> Capsule:
        """
        Create new capsule with timezone-aware unlock date.
        
        Args:
            user_id: Owner user ID
            title: Capsule title
            text_content: Text message
            unlock_date: Local unlock datetime (naive)
            timezone: IANA timezone identifier for unlock_date
            is_public: Public visibility flag
            media_urls: List of media URLs
            
        Returns:
            Created Capsule object
            
        Raises:
            InvalidUnlockDateError: If unlock_date not in future (after UTC conversion)
            InvalidTimezoneError: If timezone is not valid IANA identifier
            ValidationError: If validation fails
        """
```

### 3. TimezoneSelector (Frontend Component)

**Location:** `frontend/components/capsule/TimezoneSelector.tsx`

```typescript
interface TimezoneSelectorProps {
  value: string;
  onChange: (timezone: string) => void;
  error?: string;
}

/**
 * Searchable dropdown for selecting IANA timezone identifiers.
 * 
 * Features:
 * - Auto-detects browser timezone on mount
 * - Searchable list of all IANA timezones
 * - Groups timezones by region (America, Europe, Asia, etc.)
 * - Shows current UTC offset for each timezone
 * - Accessible with keyboard navigation
 */
export default function TimezoneSelector({
  value,
  onChange,
  error
}: TimezoneSelectorProps): JSX.Element;

/**
 * Detects the user's browser timezone using Intl API.
 * Falls back to "UTC" if detection fails.
 */
export function detectBrowserTimezone(): string;
```

### 4. UnlockDateDisplay (Frontend Utility)

**Location:** `frontend/lib/timezone.ts`

```typescript
/**
 * Formats a UTC timestamp for display in the capsule's stored timezone.
 * 
 * @param utcDate - ISO 8601 UTC timestamp string
 * @param timezone - IANA timezone identifier
 * @returns Formatted string like "Dec 25, 2024 9:00 AM EST"
 */
export function formatUnlockDate(utcDate: string, timezone: string): string;

/**
 * Gets the timezone abbreviation for a given date and timezone.
 * 
 * @param date - Date to get abbreviation for
 * @param timezone - IANA timezone identifier
 * @returns Abbreviation like "EST", "PST", "UTC"
 */
export function getTimezoneAbbreviation(date: Date, timezone: string): string;

/**
 * Converts a local datetime string to UTC ISO string.
 * Used when submitting the capsule form.
 * 
 * @param localDatetime - Local datetime string from input
 * @param timezone - IANA timezone identifier
 * @returns UTC ISO 8601 string
 */
export function localToUtc(localDatetime: string, timezone: string): string;
```

### 5. API Schema Updates

**Location:** `backend/app/schemas/capsule.py`

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

class CapsuleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text_content: Optional[str] = None
    unlock_date: datetime
    timezone: str = Field(default="UTC", max_length=64)
    is_public: bool = False
    
    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validates timezone is a valid IANA identifier"""
        from app.services.timezone_service import TimezoneService
        TimezoneService.validate_timezone(v)
        return v

class CapsuleResponse(BaseModel):
    id: int
    user_id: int
    title: str
    text_content: Optional[str]
    media_urls: list[str]
    unlock_date: datetime
    timezone: str  # New field
    status: str
    is_public: bool
    created_at: datetime
    time_until_unlock: Optional[int]
    ai_analysis: Optional[AIAnalysisResponse]
    
    # Computed field for display
    unlock_date_local: Optional[str]  # Formatted in stored timezone
```

## Data Models

### Database Schema Changes

```sql
-- Add timezone column to capsules table
ALTER TABLE capsules 
ADD COLUMN timezone VARCHAR(64) NOT NULL DEFAULT 'UTC';

-- Add check constraint for valid timezone format (basic validation)
-- Full IANA validation happens at application layer
ALTER TABLE capsules
ADD CONSTRAINT check_timezone_format 
CHECK (timezone ~ '^[A-Za-z_]+/[A-Za-z_]+$' OR timezone = 'UTC');

-- Index for potential timezone-based queries
CREATE INDEX idx_capsules_timezone ON capsules(timezone);
```

### SQLAlchemy Model Update

**Location:** `backend/app/models/capsule.py`

```python
class Capsule(Base):
    __tablename__ = "capsules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    text_content = Column(Text, nullable=True)
    media_urls = Column(JSON, default=list, nullable=False)
    transcriptions = Column(JSON, default=list, nullable=False)
    unlock_date = Column(DateTime(timezone=True), nullable=False, index=True)
    timezone = Column(String(64), nullable=False, default="UTC")  # New column
    status = Column(String(20), nullable=False, default="locked", index=True)
    is_public = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('locked', 'unlocked')", name="check_status"),
        CheckConstraint("unlock_date > created_at", name="check_future_unlock_date"),
        Index("idx_capsules_public_unlocked", "is_public", "status", "unlock_date"),
        Index("idx_capsules_timezone", "timezone"),
    )
```

### Migration Script

**Location:** `backend/alembic/versions/xxx_add_timezone_column.py`

```python
"""Add timezone column to capsules table

Revision ID: xxx
Revises: previous_revision
Create Date: 2024-xx-xx
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column(
        'capsules',
        sa.Column('timezone', sa.String(64), nullable=False, server_default='UTC')
    )
    op.create_index('idx_capsules_timezone', 'capsules', ['timezone'])

def downgrade():
    op.drop_index('idx_capsules_timezone', table_name='capsules')
    op.drop_column('capsules', 'timezone')
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Timezone Validation

*For any* string input provided as a timezone identifier, if the string is a valid IANA timezone identifier (exists in `zoneinfo.available_timezones()`), the system shall accept it; otherwise, the system shall reject it with a descriptive error message indicating the timezone is invalid.

**Validates: Requirements 2.1, 2.2, 3.4**

### Property 2: Capsule Storage Integrity

*For any* capsule created with a local datetime and timezone, the system shall store both the correctly converted UTC timestamp in `unlock_date` and the original IANA timezone identifier in the `timezone` field, such that both values are retrievable from the database record.

**Validates: Requirements 1.4, 3.1, 3.2**

### Property 3: Display Conversion with Timezone Abbreviation

*For any* capsule with a stored UTC timestamp and timezone, when displaying the unlock date, the system shall convert the UTC timestamp to the stored timezone and include the appropriate timezone abbreviation (e.g., "EST", "PST", "UTC") in the formatted output.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 4: UTC Round-Trip Preservation

*For any* valid capsule record with a stored UTC timestamp and IANA timezone, converting the UTC timestamp to the stored timezone and back to UTC shall produce the original UTC timestamp (identity operation).

**Validates: Requirements 5.3**

### Property 5: Local DateTime Round-Trip Preservation

*For any* valid IANA timezone identifier and future local datetime (excluding DST gap times), converting the local datetime to UTC using the timezone and then converting back to the same timezone shall produce the original local datetime.

**Validates: Requirements 5.4, 2.4**

### Property 6: Future Date Validation After Conversion

*For any* local datetime and timezone submitted for capsule creation, the system shall accept the request only if the UTC-converted timestamp is in the future relative to the current UTC time; otherwise, it shall reject with an appropriate error.

**Validates: Requirements 2.5**

## Error Handling

### Backend Error Handling

| Error Condition | Error Type | HTTP Status | User Message |
|----------------|------------|-------------|--------------|
| Invalid IANA timezone identifier | `InvalidTimezoneError` | 400 | "Invalid timezone: '{tz}'. Please select a valid timezone from the list." |
| Nonexistent local time (DST gap) | `NonexistentTimeError` | 200* | "The time {time} does not exist in {tz} due to daylight saving time. Adjusted to {adjusted_time}." |
| Unlock date in past after UTC conversion | `InvalidUnlockDateError` | 400 | "Unlock date must be in the future. The selected time converts to {utc_time} UTC which has already passed." |
| Ambiguous local time (DST overlap) | N/A (handled) | 200 | System silently selects first occurrence per requirement 5.1 |

*Note: Nonexistent time is auto-adjusted per requirement 5.2, returned as success with adjustment info.

### Frontend Error Handling

| Error Condition | Handling |
|----------------|----------|
| Browser timezone detection fails | Default to "UTC", no error shown |
| Invalid timezone in response | Display date in UTC with "UTC" label |
| API returns timezone validation error | Display error message below timezone selector |

### Graceful Degradation

- If stored timezone is invalid/corrupted, display falls back to UTC
- If timezone conversion fails, log error and display raw UTC timestamp
- Legacy capsules without timezone field treated as UTC

## Testing Strategy

### Unit Tests

Unit tests focus on specific examples, edge cases, and error conditions:

**Backend Unit Tests:**
- `test_validate_timezone_valid`: Test known valid timezones (America/New_York, Europe/London, Asia/Tokyo)
- `test_validate_timezone_invalid`: Test invalid strings ("Invalid/Zone", "NotATimezone", "")
- `test_convert_to_utc_basic`: Test conversion with known input/output pairs
- `test_convert_to_utc_dst_gap`: Test spring-forward DST gap adjustment (e.g., March 10, 2024 2:30 AM America/New_York)
- `test_convert_to_utc_dst_overlap`: Test fall-back DST overlap resolution (e.g., November 3, 2024 1:30 AM America/New_York)
- `test_create_capsule_with_timezone`: Test capsule creation stores timezone correctly
- `test_create_capsule_without_timezone`: Test default "UTC" is stored
- `test_create_capsule_invalid_timezone`: Test rejection with error message

**Frontend Unit Tests:**
- `test_timezone_selector_renders`: Test component renders with searchable list
- `test_timezone_selector_default_browser`: Test defaults to detected browser timezone
- `test_timezone_selector_fallback_utc`: Test fallback to UTC when detection fails
- `test_format_unlock_date`: Test formatting with various timezones
- `test_format_unlock_date_with_abbreviation`: Test abbreviation is included

### Property-Based Tests

Property-based tests verify universal properties across randomly generated inputs. Each test runs minimum 100 iterations.

**Test Configuration:**
- Library: `hypothesis` (Python backend), `fast-check` (TypeScript frontend)
- Minimum iterations: 100 per property
- Shrinking enabled for minimal failing examples

**Backend Property Tests:**

```python
# Feature: timezone-selection, Property 1: Timezone Validation
@given(st.text())
def test_timezone_validation_property(timezone_str):
    """For any string, valid IANA timezones are accepted, invalid ones rejected."""
    from zoneinfo import available_timezones
    is_valid = timezone_str in available_timezones()
    
    if is_valid:
        assert TimezoneService.validate_timezone(timezone_str) == True
    else:
        with pytest.raises(InvalidTimezoneError):
            TimezoneService.validate_timezone(timezone_str)

# Feature: timezone-selection, Property 4: UTC Round-Trip Preservation
@given(
    st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
    st.sampled_from(list(available_timezones()))
)
def test_utc_roundtrip_property(utc_dt, timezone):
    """UTC -> local -> UTC produces original UTC timestamp."""
    utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    local_dt = TimezoneService.convert_from_utc(utc_dt, timezone)
    roundtrip_utc = TimezoneService.convert_to_utc(local_dt.replace(tzinfo=None), timezone)
    assert roundtrip_utc == utc_dt

# Feature: timezone-selection, Property 5: Local DateTime Round-Trip Preservation
@given(
    st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
    st.sampled_from(list(available_timezones()))
)
def test_local_roundtrip_property(local_dt, timezone):
    """Local -> UTC -> local preserves original (excluding DST gaps)."""
    try:
        utc_dt = TimezoneService.convert_to_utc(local_dt, timezone)
        roundtrip_local = TimezoneService.convert_from_utc(utc_dt, timezone)
        # Compare without tzinfo for naive comparison
        assert roundtrip_local.replace(tzinfo=None) == local_dt
    except NonexistentTimeError:
        pass  # DST gap times are excluded from this property

# Feature: timezone-selection, Property 6: Future Date Validation
@given(
    st.datetimes(),
    st.sampled_from(list(available_timezones()))
)
def test_future_date_validation_property(local_dt, timezone):
    """Only accepts if UTC conversion is in the future."""
    utc_dt = TimezoneService.convert_to_utc(local_dt, timezone)
    is_future = utc_dt > datetime.now(ZoneInfo("UTC"))
    
    if is_future:
        # Should succeed
        capsule = CapsuleService.create_capsule(..., unlock_date=local_dt, timezone=timezone)
        assert capsule is not None
    else:
        # Should fail
        with pytest.raises(InvalidUnlockDateError):
            CapsuleService.create_capsule(..., unlock_date=local_dt, timezone=timezone)
```

**Frontend Property Tests:**

```typescript
// Feature: timezone-selection, Property 3: Display Conversion with Abbreviation
fc.assert(
  fc.property(
    fc.date({ min: new Date('2020-01-01'), max: new Date('2030-12-31') }),
    fc.constantFrom(...IANA_TIMEZONES),
    (utcDate, timezone) => {
      const formatted = formatUnlockDate(utcDate.toISOString(), timezone);
      const abbrev = getTimezoneAbbreviation(utcDate, timezone);
      // Formatted string must include the timezone abbreviation
      expect(formatted).toContain(abbrev);
    }
  ),
  { numRuns: 100 }
);
```

### Integration Tests

- Test full capsule creation flow with timezone through API
- Test capsule retrieval returns correct timezone and formatted date
- Test dashboard displays multiple capsules with different timezones correctly
- Test migration: existing capsules without timezone display correctly as UTC
