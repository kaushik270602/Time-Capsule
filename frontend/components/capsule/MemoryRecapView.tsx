"use client";

import React from "react";
import SentimentBadge from "./SentimentBadge";

interface MemoryRecapViewProps {
  recapText: string;
  sentimentLabel?: string | null;
  sentimentConfidence?: number | null;
  toneDescription?: string | null;
}

export default function MemoryRecapView({
  recapText,
  sentimentLabel,
  sentimentConfidence,
  toneDescription,
}: MemoryRecapViewProps) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-violet-50 via-purple-50 to-fuchsia-50 border border-violet-200 p-6">
      {/* Decorative elements */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-violet-100/50 to-transparent rounded-bl-full" />
      <div className="absolute bottom-0 left-0 w-24 h-24 bg-gradient-to-tr from-fuchsia-100/50 to-transparent rounded-tr-full" />

      <div className="relative space-y-4">
        <div className="flex items-center gap-2">
          <span className="text-xl" aria-hidden="true">✨</span>
          <h2 className="text-lg font-semibold text-violet-900">Memory Recap</h2>
        </div>

        <p className="text-violet-800 leading-relaxed whitespace-pre-wrap">
          {recapText}
        </p>

        {sentimentLabel && sentimentLabel !== "neutral" && (
          <div className="pt-2">
            <SentimentBadge
              label={sentimentLabel}
              confidence={sentimentConfidence ?? 0}
              toneDescription={toneDescription ?? ""}
            />
          </div>
        )}
      </div>
    </div>
  );
}
