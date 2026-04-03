"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { CapsuleResponse } from "@/lib/api";
import { formatUnlockDate } from "@/lib/timezone";

interface CapsuleCardProps {
  capsule: CapsuleResponse;
}

function computeCountdown(unlockDate: string): string {
  const now = Date.now();
  const target = new Date(unlockDate).getTime();
  const diff = target - now;
  if (diff <= 0) return "Unlocking soon…";

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  parts.push(`${minutes}m`);
  return parts.join(" ");
}

export default function CapsuleCard({ capsule }: CapsuleCardProps) {
  const isLocked = capsule.status === "locked";
  const [countdown, setCountdown] = useState(() =>
    isLocked ? computeCountdown(capsule.unlock_date) : ""
  );

  useEffect(() => {
    if (!isLocked) return;
    const id = setInterval(() => {
      setCountdown(computeCountdown(capsule.unlock_date));
    }, 60_000);
    return () => clearInterval(id);
  }, [isLocked, capsule.unlock_date]);

  return (
    <Link
      href={`/capsules/${capsule.id}`}
      className={`block rounded-xl border p-4 transition-colors hover:shadow-md ${
        isLocked
          ? "border-amber-200 bg-amber-50/40 hover:bg-amber-50"
          : "border-emerald-200 bg-emerald-50/40 hover:bg-emerald-50"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span
            className={`flex-shrink-0 inline-flex items-center justify-center w-10 h-10 rounded-lg text-lg ${
              isLocked ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"
            }`}
            aria-hidden="true"
          >
            {isLocked ? "🔒" : "🔓"}
          </span>
          <div className="min-w-0">
            <p className="font-medium text-stone-900 truncate">{capsule.title}</p>
            <p className="text-xs text-stone-500 mt-0.5">
              {isLocked
                ? `Unlocks ${formatUnlockDate(capsule.unlock_date, capsule.timezone || 'UTC')}`
                : `Unlocked ${formatUnlockDate(capsule.unlock_date, capsule.timezone || 'UTC')}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {capsule.is_public ? (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
              Public
            </span>
          ) : (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-stone-100 text-stone-600">
              Private
            </span>
          )}
          <span
            className={`text-xs font-medium px-2.5 py-1 rounded-full ${
              isLocked ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"
            }`}
          >
            {capsule.status}
          </span>
        </div>
      </div>

      {isLocked && countdown && (
        <div className="mt-3 flex items-center gap-2 text-sm text-amber-700">
          <span aria-hidden="true">⏳</span>
          <span>{countdown}</span>
        </div>
      )}
    </Link>
  );
}
