"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { detectBrowserTimezone } from "@/lib/timezone";

interface TimezoneSelectorProps {
  value: string;
  onChange: (timezone: string) => void;
  error?: string;
}

interface TimezoneOption {
  id: string;
  label: string;
  offset: string;
  region: string;
}

// Common IANA timezones grouped by region
const TIMEZONE_DATA: string[] = [
  // Africa
  "Africa/Cairo", "Africa/Casablanca", "Africa/Johannesburg", "Africa/Lagos", "Africa/Nairobi",
  // America
  "America/Anchorage", "America/Argentina/Buenos_Aires", "America/Bogota", "America/Chicago",
  "America/Denver", "America/Halifax", "America/Lima", "America/Los_Angeles", "America/Mexico_City",
  "America/New_York", "America/Phoenix", "America/Santiago", "America/Sao_Paulo", "America/Toronto",
  "America/Vancouver",
  // Asia
  "Asia/Bangkok", "Asia/Colombo", "Asia/Dubai", "Asia/Hong_Kong", "Asia/Jakarta", "Asia/Jerusalem",
  "Asia/Karachi", "Asia/Kolkata", "Asia/Kuala_Lumpur", "Asia/Manila", "Asia/Seoul", "Asia/Shanghai",
  "Asia/Singapore", "Asia/Taipei", "Asia/Tokyo",
  // Atlantic
  "Atlantic/Azores", "Atlantic/Reykjavik",
  // Australia
  "Australia/Adelaide", "Australia/Brisbane", "Australia/Darwin", "Australia/Melbourne",
  "Australia/Perth", "Australia/Sydney",
  // Europe
  "Europe/Amsterdam", "Europe/Athens", "Europe/Berlin", "Europe/Brussels", "Europe/Budapest",
  "Europe/Dublin", "Europe/Helsinki", "Europe/Istanbul", "Europe/Lisbon", "Europe/London",
  "Europe/Madrid", "Europe/Moscow", "Europe/Paris", "Europe/Prague", "Europe/Rome",
  "Europe/Stockholm", "Europe/Vienna", "Europe/Warsaw", "Europe/Zurich",
  // Indian
  "Indian/Maldives", "Indian/Mauritius",
  // Pacific
  "Pacific/Auckland", "Pacific/Fiji", "Pacific/Guam", "Pacific/Honolulu", "Pacific/Samoa",
  // UTC
  "UTC"
];

/**
 * Gets the UTC offset string for a timezone (e.g., "UTC-05:00")
 */
function getUtcOffset(timezone: string): string {
  try {
    const now = new Date();
    const formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: timezone,
      timeZoneName: "shortOffset",
    });
    const parts = formatter.formatToParts(now);
    const offsetPart = parts.find((p) => p.type === "timeZoneName");
    return offsetPart?.value || "UTC";
  } catch {
    return "UTC";
  }
}

/**
 * Extracts region from IANA timezone (e.g., "America/New_York" -> "America")
 */
function getRegion(timezone: string): string {
  if (timezone === "UTC") return "UTC";
  const parts = timezone.split("/");
  return parts[0] || "Other";
}

/**
 * Formats timezone for display (e.g., "America/New_York" -> "New York")
 */
function formatTimezoneLabel(timezone: string): string {
  if (timezone === "UTC") return "UTC";
  const parts = timezone.split("/");
  const city = parts[parts.length - 1];
  return city.replace(/_/g, " ");
}

/**
 * Searchable dropdown for selecting IANA timezone identifiers.
 */
export default function TimezoneSelector({
  value,
  onChange,
  error,
}: TimezoneSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Build timezone options with offset and region
  const timezoneOptions: TimezoneOption[] = useMemo(() => {
    return TIMEZONE_DATA.map((tz) => ({
      id: tz,
      label: formatTimezoneLabel(tz),
      offset: getUtcOffset(tz),
      region: getRegion(tz),
    }));
  }, []);

  // Filter options based on search
  const filteredOptions = useMemo(() => {
    if (!search.trim()) return timezoneOptions;
    const searchLower = search.toLowerCase();
    return timezoneOptions.filter(
      (opt) =>
        opt.id.toLowerCase().includes(searchLower) ||
        opt.label.toLowerCase().includes(searchLower) ||
        opt.region.toLowerCase().includes(searchLower)
    );
  }, [timezoneOptions, search]);

  // Group filtered options by region
  const groupedOptions = useMemo(() => {
    const groups: Record<string, TimezoneOption[]> = {};
    for (const opt of filteredOptions) {
      if (!groups[opt.region]) {
        groups[opt.region] = [];
      }
      groups[opt.region].push(opt);
    }
    // Sort regions alphabetically, but keep UTC at the end
    const sortedRegions = Object.keys(groups).sort((a, b) => {
      if (a === "UTC") return 1;
      if (b === "UTC") return -1;
      return a.localeCompare(b);
    });
    return sortedRegions.map((region) => ({
      region,
      options: groups[region],
    }));
  }, [filteredOptions]);

  // Flat list for keyboard navigation
  const flatOptions = useMemo(() => {
    return groupedOptions.flatMap((g) => g.options);
  }, [groupedOptions]);

  // Auto-detect browser timezone on mount if no value
  useEffect(() => {
    if (!value) {
      const detected = detectBrowserTimezone();
      // Check if detected timezone is in our list, otherwise use UTC
      const isValid = TIMEZONE_DATA.includes(detected);
      onChange(isValid ? detected : "UTC");
    }
  }, [value, onChange]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Scroll highlighted option into view
  useEffect(() => {
    if (isOpen && listRef.current && highlightedIndex >= 0) {
      const items = listRef.current.querySelectorAll('[role="option"]');
      const item = items[highlightedIndex] as HTMLElement;
      if (item) {
        item.scrollIntoView({ block: "nearest" });
      }
    }
  }, [highlightedIndex, isOpen]);

  // Reset highlight when search changes
  useEffect(() => {
    setHighlightedIndex(0);
  }, [search]);

  const handleSelect = useCallback(
    (timezone: string) => {
      onChange(timezone);
      setIsOpen(false);
      setSearch("");
    },
    [onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen) {
        if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
          e.preventDefault();
          setIsOpen(true);
        }
        return;
      }

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setHighlightedIndex((prev) =>
            prev < flatOptions.length - 1 ? prev + 1 : prev
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : 0));
          break;
        case "Enter":
          e.preventDefault();
          if (flatOptions[highlightedIndex]) {
            handleSelect(flatOptions[highlightedIndex].id);
          }
          break;
        case "Escape":
          e.preventDefault();
          setIsOpen(false);
          setSearch("");
          break;
        case "Tab":
          setIsOpen(false);
          setSearch("");
          break;
      }
    },
    [isOpen, flatOptions, highlightedIndex, handleSelect]
  );

  // Get display value for the selected timezone
  const selectedOption = timezoneOptions.find((opt) => opt.id === value);
  const displayValue = selectedOption
    ? `${selectedOption.label} (${selectedOption.offset})`
    : value || "Select timezone";

  return (
    <div ref={containerRef} className="relative">
      <label
        id="timezone-label"
        className="block text-sm font-medium text-gray-700 mb-1"
      >
        Timezone
      </label>

      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-labelledby="timezone-label"
        aria-invalid={!!error}
        aria-describedby={error ? "timezone-error" : undefined}
        className={`w-full px-3 py-2 text-left border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white ${
          error ? "border-red-500" : "border-gray-300"
        }`}
      >
        <span className="block truncate">{displayValue}</span>
        <span className="absolute inset-y-0 right-0 flex items-center pr-2 pt-6 pointer-events-none">
          <svg
            className={`h-5 w-5 text-gray-400 transition-transform ${
              isOpen ? "rotate-180" : ""
            }`}
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
              clipRule="evenodd"
            />
          </svg>
        </span>
      </button>

      {/* Error message */}
      {error && (
        <p id="timezone-error" className="mt-1 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-lg shadow-lg">
          {/* Search input */}
          <div className="p-2 border-b border-gray-200">
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search timezones..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              aria-label="Search timezones"
              autoFocus
            />
          </div>

          {/* Options list */}
          <ul
            ref={listRef}
            role="listbox"
            aria-labelledby="timezone-label"
            className="max-h-60 overflow-auto py-1"
          >
            {groupedOptions.length === 0 ? (
              <li className="px-3 py-2 text-sm text-gray-500">
                No timezones found
              </li>
            ) : (
              groupedOptions.map((group) => (
                <li key={group.region}>
                  {/* Region header */}
                  <div className="px-3 py-1 text-xs font-semibold text-gray-500 bg-gray-50 sticky top-0">
                    {group.region}
                  </div>
                  {/* Region options */}
                  {group.options.map((opt) => {
                    const optionIndex = flatOptions.findIndex(
                      (f) => f.id === opt.id
                    );
                    const isHighlighted = optionIndex === highlightedIndex;
                    const isSelected = opt.id === value;

                    return (
                      <div
                        key={opt.id}
                        role="option"
                        aria-selected={isSelected}
                        onClick={() => handleSelect(opt.id)}
                        onMouseEnter={() => setHighlightedIndex(optionIndex)}
                        className={`px-3 py-2 cursor-pointer flex justify-between items-center ${
                          isHighlighted ? "bg-indigo-50" : ""
                        } ${isSelected ? "bg-indigo-100" : ""}`}
                      >
                        <span className="text-sm text-gray-900">{opt.label}</span>
                        <span className="text-xs text-gray-500">{opt.offset}</span>
                      </div>
                    );
                  })}
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
