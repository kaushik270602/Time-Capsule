/**
 * Timezone utility functions for capsule unlock date handling.
 * Uses date-fns-tz for timezone-aware formatting and conversion.
 */

import { format } from 'date-fns';
import { formatInTimeZone, utcToZonedTime, zonedTimeToUtc } from 'date-fns-tz';

/**
 * Detects the user's browser timezone using Intl API.
 * Falls back to "UTC" if detection fails.
 * 
 * @returns IANA timezone identifier (e.g., "America/New_York")
 */
export function detectBrowserTimezone(): string {
  try {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return timezone || 'UTC';
  } catch {
    return 'UTC';
  }
}

/**
 * Gets the timezone abbreviation for a given date and timezone.
 * 
 * @param date - Date to get abbreviation for
 * @param timezone - IANA timezone identifier
 * @returns Abbreviation like "EST", "PST", "UTC"
 */
export function getTimezoneAbbreviation(date: Date, timezone: string): string {
  try {
    return formatInTimeZone(date, timezone, 'zzz');
  } catch {
    return 'UTC';
  }
}

/**
 * Formats a UTC timestamp for display in the capsule's stored timezone.
 * 
 * @param utcDate - ISO 8601 UTC timestamp string
 * @param timezone - IANA timezone identifier
 * @returns Formatted string like "Dec 25, 2024 9:00 AM EST"
 */
export function formatUnlockDate(utcDate: string, timezone: string): string {
  try {
    const date = new Date(utcDate);
    const formatted = formatInTimeZone(date, timezone, 'MMM d, yyyy h:mm a');
    const abbrev = getTimezoneAbbreviation(date, timezone);
    return `${formatted} ${abbrev}`;
  } catch {
    // Fallback to UTC display if timezone is invalid
    const date = new Date(utcDate);
    const formatted = format(date, 'MMM d, yyyy h:mm a');
    return `${formatted} UTC`;
  }
}

/**
 * Converts a local datetime string to UTC ISO string.
 * Used when submitting the capsule form.
 * 
 * @param localDatetime - Local datetime string from input (e.g., "2024-12-25T09:00")
 * @param timezone - IANA timezone identifier
 * @returns UTC ISO 8601 string
 */
export function localToUtc(localDatetime: string, timezone: string): string {
  try {
    // Parse the local datetime string as a date in the specified timezone
    const localDate = new Date(localDatetime);
    // zonedTimeToUtc interprets the date as being in the specified timezone
    // and converts it to UTC
    const utcDate = zonedTimeToUtc(localDate, timezone);
    return utcDate.toISOString();
  } catch {
    // Fallback: treat as UTC if conversion fails
    return new Date(localDatetime).toISOString();
  }
}
