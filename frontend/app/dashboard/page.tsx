"use client";

import React, { useEffect, useMemo, useState } from "react";
import { capsuleApi, CapsuleResponse } from "@/lib/api";
import StatsCards from "@/components/dashboard/StatsCards";
import CapsuleList from "@/components/dashboard/CapsuleList";
import FilterBar, { StatusFilter } from "@/components/dashboard/FilterBar";

function filterCapsules(
  capsules: CapsuleResponse[],
  statusFilter: StatusFilter,
  searchQuery: string
): CapsuleResponse[] {
  let result = capsules;

  if (statusFilter !== "all") {
    result = result.filter((c) => c.status === statusFilter);
  }

  const query = searchQuery.trim().toLowerCase();
  if (query) {
    result = result.filter((c) => {
      const titleMatch = c.title.toLowerCase().includes(query);
      const contentMatch =
        c.text_content != null &&
        c.text_content.toLowerCase().includes(query);
      return titleMatch || contentMatch;
    });
  }

  return result;
}

export default function DashboardPage() {
  const [capsules, setCapsules] = useState<CapsuleResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const fetchCapsules = async () => {
      try {
        const { data } = await capsuleApi.list();
        setCapsules(data.capsules);
      } catch {
        setError("Failed to load capsules.");
      } finally {
        setLoading(false);
      }
    };
    fetchCapsules();
  }, []);

  const filteredCapsules = useMemo(
    () => filterCapsules(capsules, statusFilter, searchQuery),
    [capsules, statusFilter, searchQuery]
  );

  const total = capsules.length;
  const locked = capsules.filter((c) => c.status === "locked").length;
  const unlocked = capsules.filter((c) => c.status === "unlocked").length;

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-stone-900">Dashboard</h1>
        <p className="mt-1 text-sm text-stone-500">
          Overview of your time capsules
        </p>
      </div>

      <StatsCards total={total} locked={locked} unlocked={unlocked} loading={loading} />

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
          {error}
        </div>
      )}

      {!loading && (
        <>
          <FilterBar
            statusFilter={statusFilter}
            searchQuery={searchQuery}
            onStatusChange={setStatusFilter}
            onSearchChange={setSearchQuery}
          />
          <CapsuleList capsules={filteredCapsules} />
        </>
      )}
    </div>
  );
}
