# Requirements Document: Timezone Selection for Capsule Unlock Dates

## Introduction

This feature extends the TimeLock application to allow users to select a timezone when setting the unlock date for a time capsule. Currently, the system stores all unlock dates as UTC timestamps but provides no mechanism for users to specify their local timezone, meaning the unlock time may not correspond to the user's intended local time. This feature adds timezone awareness to capsule creation and display, ensuring capsules unlock at the correct local time as intended by the user.

## Glossary

- **System**: The TimeLock application (frontend and backend combined)
- **Capsule_Form**: The frontend form component used to create a new time capsule
- **Timezone_Selector**: A UI component that allows users to pick a timezone from a list of IANA timezone identifiers
- **IANA_Timezone**: A timezone identifier from the IANA Time Zone Database (e.g., "America/New_York", "Europe/London")
- **User_Timezone**: The timezone selected by the user for a specific capsule's unlock date
- **Browser_Timezone**: The timezone detected from the user's browser via the Intl API
- **UTC_Timestamp**: A datetime value stored in Coordinated Universal Time
- **Capsule_Service**: The backend service responsible for capsule creation, validation, and retrieval
- **Unlock_Display**: The UI representation of a capsule's unlock date shown to the user

## Requirements

### Requirement 1: Timezone Selection During Capsule Creation

**User Story:** As a user, I want to select a timezone when setting the unlock date for my capsule, so that the capsule unlocks at the correct local time I intended.

#### Acceptance Criteria

1. WHEN a user opens the Capsule_Form, THE Timezone_Selector SHALL display a searchable list of IANA_Timezone identifiers
2. WHEN the Capsule_Form loads, THE Timezone_Selector SHALL default to the Browser_Timezone detected from the user's environment
3. WHEN a user selects an IANA_Timezone from the Timezone_Selector, THE Capsule_Form SHALL associate the selected timezone with the unlock date input
4. WHEN a user submits the Capsule_Form with a selected timezone, THE System SHALL convert the local unlock date and time to a UTC_Timestamp using the selected IANA_Timezone before storing
5. IF the Browser_Timezone cannot be detected, THEN THE Timezone_Selector SHALL default to "UTC"

### Requirement 2: Timezone Validation

**User Story:** As a user, I want the system to validate my timezone selection, so that invalid timezones are rejected and my capsule unlock time is accurate.

#### Acceptance Criteria

1. WHEN a capsule creation request includes a timezone field, THE Capsule_Service SHALL validate that the timezone is a valid IANA_Timezone identifier
2. IF an invalid timezone identifier is provided, THEN THE Capsule_Service SHALL reject the request and return a descriptive error message
3. WHEN a capsule creation request omits the timezone field, THE Capsule_Service SHALL treat the unlock date as UTC
4. WHEN the Capsule_Service converts a local datetime to UTC, THE Capsule_Service SHALL account for daylight saving time rules of the selected IANA_Timezone
5. WHEN the Capsule_Service validates the unlock date, THE Capsule_Service SHALL verify the date is in the future after conversion to UTC

### Requirement 3: Timezone Storage

**User Story:** As a system administrator, I want the selected timezone to be stored alongside the capsule, so that the original user intent can be preserved for display purposes.

#### Acceptance Criteria

1. WHEN a capsule is created with a selected timezone, THE System SHALL store the IANA_Timezone identifier in the capsule record
2. THE System SHALL continue to store the unlock_date as a UTC_Timestamp in the database
3. WHEN a capsule is created without a timezone selection, THE System SHALL store "UTC" as the default timezone value
4. THE System SHALL enforce that stored timezone values are valid IANA_Timezone identifiers via schema validation

### Requirement 4: Timezone-Aware Unlock Date Display

**User Story:** As a user, I want to see capsule unlock dates displayed in the timezone I originally selected, so that the displayed time matches my original intent.

#### Acceptance Criteria

1. WHEN a user views a capsule's unlock date, THE Unlock_Display SHALL convert the UTC_Timestamp to the capsule's stored IANA_Timezone for display
2. WHEN a user views the capsule list on the dashboard, THE Unlock_Display SHALL show each capsule's unlock date in the capsule's stored timezone
3. WHEN displaying an unlock date, THE Unlock_Display SHALL include the timezone abbreviation (e.g., "EST", "PST") alongside the formatted date and time
4. WHEN a capsule has no stored timezone, THE Unlock_Display SHALL display the unlock date in UTC with a "UTC" label

### Requirement 5: Timezone Conversion Correctness

**User Story:** As a user, I want timezone conversions to be accurate across daylight saving time transitions, so that my capsule unlocks at the exact local time I specified.

#### Acceptance Criteria

1. WHEN a user sets an unlock date that falls during a daylight saving time transition in the selected IANA_Timezone, THE Capsule_Service SHALL resolve the ambiguity by selecting the first occurrence of the local time
2. IF a user sets an unlock date to a local time that does not exist due to a daylight saving time spring-forward transition, THEN THE Capsule_Service SHALL adjust the time forward to the next valid local time and inform the user of the adjustment
3. FOR ALL valid capsule records, converting the stored UTC_Timestamp to the stored IANA_Timezone and back to UTC SHALL produce the original UTC_Timestamp (round-trip property)
4. FOR ALL valid IANA_Timezone identifiers and future dates, THE Capsule_Service SHALL produce a UTC_Timestamp that, when converted back to the selected timezone, matches the user's original local date and time input
