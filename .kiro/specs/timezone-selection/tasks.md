# Implementation Plan: Timezone Selection for Capsule Unlock Dates

## Overview

This implementation adds timezone awareness to capsule creation and display. Users can select a timezone when setting unlock dates, and the system stores both the UTC timestamp and the original timezone for accurate display. The backend uses Python's `zoneinfo` module, and the frontend uses `date-fns-tz` for timezone handling.

## Tasks

- [x] 1. Database schema and model updates
  - [x] 1.1 Add timezone column to Capsule model
    - Add `timezone` column (String(64), default "UTC") to `backend/app/models/capsule.py`
    - Add index for timezone column
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 1.2 Create database migration for timezone column
    - Create Alembic migration to add `timezone` column with default "UTC"
    - Ensure existing capsules get "UTC" as default value
    - _Requirements: 3.1, 3.3_

- [x] 2. Backend TimezoneService implementation
  - [x] 2.1 Create TimezoneService with validation and conversion methods
    - Create `backend/app/services/timezone_service.py`
    - Implement `validate_timezone()` using `zoneinfo.available_timezones()`
    - Implement `convert_to_utc()` with DST handling
    - Implement `convert_from_utc()` for display conversion
    - Implement `get_timezone_abbreviation()`
    - Implement `adjust_nonexistent_time()` for DST gap handling
    - Define `InvalidTimezoneError`, `NonexistentTimeError` exceptions
    - _Requirements: 2.1, 2.2, 2.4, 5.1, 5.2_

  - [x] 2.2 Write property test for timezone validation
    - **Property 1: Timezone Validation**
    - **Validates: Requirements 2.1, 2.2, 3.4**

  - [x] 2.3 Write property test for UTC round-trip preservation
    - **Property 4: UTC Round-Trip Preservation**
    - **Validates: Requirements 5.3**

  - [x] 2.4 Write property test for local datetime round-trip preservation
    - **Property 5: Local DateTime Round-Trip Preservation**
    - **Validates: Requirements 5.4, 2.4**

- [x] 3. Checkpoint - Ensure TimezoneService tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Backend API schema and service updates
  - [x] 4.1 Update Pydantic schemas for timezone field
    - Add `timezone` field to `CapsuleCreate` schema with validator
    - Add `timezone` and `unlock_date_local` fields to `CapsuleResponse` schema
    - _Requirements: 2.1, 2.2, 2.3, 4.1_

  - [x] 4.2 Update CapsuleService to handle timezone
    - Modify `create_capsule()` to accept timezone parameter
    - Integrate TimezoneService for validation and UTC conversion
    - Validate unlock date is in future after UTC conversion
    - Store timezone with capsule record
    - _Requirements: 1.4, 2.3, 2.5, 3.1, 3.2_

  - [x] 4.3 Update capsule router endpoints
    - Update create capsule endpoint to accept timezone
    - Update response serialization to include timezone and formatted local date
    - Handle DST adjustment responses per requirement 5.2
    - _Requirements: 1.4, 4.1, 4.2, 5.2_

  - [ ]* 4.4 Write property test for future date validation
    - **Property 6: Future Date Validation After Conversion**
    - **Validates: Requirements 2.5**

  - [ ]* 4.5 Write property test for capsule storage integrity
    - **Property 2: Capsule Storage Integrity**
    - **Validates: Requirements 1.4, 3.1, 3.2**

- [x] 5. Checkpoint - Ensure backend API tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Frontend timezone utilities
  - [x] 6.1 Create timezone utility functions
    - Create `frontend/lib/timezone.ts`
    - Implement `detectBrowserTimezone()` using Intl API with UTC fallback
    - Implement `formatUnlockDate()` for display formatting with abbreviation
    - Implement `getTimezoneAbbreviation()`
    - Implement `localToUtc()` for form submission
    - _Requirements: 1.2, 1.5, 4.1, 4.3, 4.4_

  - [ ]* 6.2 Write property test for display conversion with abbreviation
    - **Property 3: Display Conversion with Timezone Abbreviation**
    - **Validates: Requirements 4.1, 4.2, 4.3**

- [x] 7. Frontend TimezoneSelector component
  - [x] 7.1 Create TimezoneSelector component
    - Create `frontend/components/capsule/TimezoneSelector.tsx`
    - Implement searchable dropdown with IANA timezone list
    - Group timezones by region (America, Europe, Asia, etc.)
    - Show current UTC offset for each timezone
    - Auto-detect and default to browser timezone on mount
    - Ensure keyboard navigation accessibility
    - _Requirements: 1.1, 1.2, 1.3, 1.5_

  - [ ]* 7.2 Write unit tests for TimezoneSelector
    - Test component renders with searchable list
    - Test defaults to detected browser timezone
    - Test fallback to UTC when detection fails
    - _Requirements: 1.1, 1.2, 1.5_

- [x] 8. Frontend CapsuleForm integration
  - [x] 8.1 Integrate TimezoneSelector into CapsuleForm
    - Add TimezoneSelector to `frontend/components/capsule/CapsuleForm.tsx`
    - Associate selected timezone with unlock date input
    - Submit timezone with capsule creation request
    - Handle timezone validation errors from API
    - _Requirements: 1.1, 1.3, 1.4_

  - [x] 8.2 Update capsule display components
    - Update dashboard and capsule detail views to use `formatUnlockDate()`
    - Display unlock dates in stored timezone with abbreviation
    - Handle capsules without timezone (display as UTC)
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend uses Python's `zoneinfo` module (standard library in Python 3.9+)
- Frontend uses `date-fns-tz` for timezone-aware formatting
- Property tests use `hypothesis` (Python) and `fast-check` (TypeScript)
- Existing capsules without timezone field are treated as UTC
- DST ambiguous times resolve to first occurrence per requirement 5.1
- DST gap times are auto-adjusted forward per requirement 5.2
