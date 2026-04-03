"use client";

import React from "react";

export type StatusFilter = "all" | "locked" | "unlocked";

interface FilterBarProps {
  statusFilter: StatusFilter;
  searchQuery: string;
  onStatusChange: (status: StatusFilter) => void;
  onSearchChange: (query: string) => void;
}

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "locked", label: "Locked" },
  { value: "unlocked", label: "Unlocked" },
];

export default function FilterBar({
  statusFilter,
  searchQuery,
  onStatusChange,
  onSearchChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-col gap-3">
      {/* Segmented filter buttons */}
      <div className="flex rounded-lg border border-stone-300 bg-white overflow-hidden" role="radiogroup" aria-label="Filter by status">
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={statusFilter === opt.value}
            onClick={() => onStatusChange(opt.value)}
            className={`flex-1 py-2 px-3 text-sm font-medium transition-colors ${
              statusFilter === opt.value
                ? "bg-amber-500 text-white"
                : "text-stone-600 hover:bg-stone-50"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Search input */}
      <div className="relative">
        <label htmlFor="capsule-search" className="sr-only">
          Search capsules
        </label>
        <input
          id="capsule-search"
          type="text"
          placeholder="Search by title or content…"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full rounded-lg border border-stone-300 bg-white py-2 pl-10 pr-3 text-sm text-stone-900 placeholder-stone-400 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
        />
        <svg
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z"
          />
        </svg>
      </div>
    </div>
  );
}
