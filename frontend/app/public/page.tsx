"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { capsuleApi, PublicCapsuleResponse } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { formatUnlockDate } from "@/lib/timezone";

const PAGE_SIZE = 20;

function truncate(text: string, maxLen = 140): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "…";
}

export default function PublicFeedPage() {
  const { user } = useAuth();
  const [capsules, setCapsules] = useState<PublicCapsuleResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);

  const fetchPage = useCallback(async (offset: number, append: boolean) => {
    try {
      const { data } = await capsuleApi.publicFeed(PAGE_SIZE, offset);
      const fetched = data.capsules;
      setCapsules((prev) => (append ? [...prev, ...fetched] : fetched));
      setHasMore(fetched.length === PAGE_SIZE);
    } catch {
      setError("Failed to load public capsules.");
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await fetchPage(0, false);
      setLoading(false);
    };
    init();
  }, [fetchPage]);

  const loadMore = async () => {
    setLoadingMore(true);
    await fetchPage(capsules.length, true);
    setLoadingMore(false);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-indigo-600">
            TimeLock
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            {user ? (
              <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
                Dashboard
              </Link>
            ) : (
              <>
                <Link href="/login" className="text-gray-600 hover:text-gray-900">
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-white hover:bg-indigo-700"
                >
                  Sign Up
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-8">
        {/* Page title */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Public Feed</h1>
          <p className="mt-1 text-sm text-gray-500">
            Recently unlocked time capsules shared by the community
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
            {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-4" data-testid="loading-skeleton">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse bg-white rounded-xl border border-gray-200 p-5 space-y-3"
              >
                <div className="h-5 bg-gray-200 rounded w-1/3" />
                <div className="h-4 bg-gray-100 rounded w-1/4" />
                <div className="h-4 bg-gray-100 rounded w-full" />
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && capsules.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">No public capsules yet</p>
            <p className="text-sm mt-1">
              Be the first to share a time capsule with the community!
            </p>
          </div>
        )}

        {/* Capsule list */}
        {!loading && capsules.length > 0 && (
          <div className="space-y-4">
            {capsules.map((c) => (
              <Link
                key={c.id}
                href={`/capsules/${c.id}`}
                className="block bg-white rounded-xl border border-gray-200 p-5 transition-colors hover:shadow-md hover:border-indigo-200"
              >
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                  <div className="min-w-0">
                    <h2 className="font-semibold text-gray-900 truncate">
                      {c.title}
                    </h2>
                    <p className="text-xs text-gray-500 mt-1">
                      by User #{c.user_id} · Unlocked {formatUnlockDate(c.unlock_date, c.timezone || 'UTC')}
                    </p>
                  </div>
                  <span className="flex-shrink-0 text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700">
                    unlocked
                  </span>
                </div>
                {c.text_content && (
                  <p className="mt-3 text-sm text-gray-600 leading-relaxed">
                    {truncate(c.text_content)}
                  </p>
                )}
              </Link>
            ))}
          </div>
        )}

        {/* Load more */}
        {!loading && hasMore && capsules.length > 0 && (
          <div className="flex justify-center pt-4">
            <button
              onClick={loadMore}
              disabled={loadingMore}
              className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loadingMore ? "Loading…" : "Load More"}
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
