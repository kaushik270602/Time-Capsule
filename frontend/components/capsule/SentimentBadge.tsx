"use client";

import React from "react";

interface SentimentBadgeProps {
  label: string;
  confidence: number;
  toneDescription: string;
}

const SENTIMENT_CONFIG: Record<string, { emoji: string; bg: string; text: string }> = {
  joyful: { emoji: "😊", bg: "bg-amber-100", text: "text-amber-800" },
  nostalgic: { emoji: "🥹", bg: "bg-purple-100", text: "text-purple-800" },
  hopeful: { emoji: "🌟", bg: "bg-emerald-100", text: "text-emerald-800" },
  reflective: { emoji: "🤔", bg: "bg-sky-100", text: "text-sky-800" },
  anxious: { emoji: "😰", bg: "bg-orange-100", text: "text-orange-800" },
  sad: { emoji: "😢", bg: "bg-stone-200", text: "text-stone-700" },
  excited: { emoji: "🎉", bg: "bg-rose-100", text: "text-rose-800" },
  neutral: { emoji: "😐", bg: "bg-stone-100", text: "text-stone-600" },
};

export default function SentimentBadge({ label, confidence, toneDescription }: SentimentBadgeProps) {
  const config = SENTIMENT_CONFIG[label] || SENTIMENT_CONFIG.neutral;

  return (
    <div className={`inline-flex flex-col gap-1 rounded-xl px-4 py-3 ${config.bg}`}>
      <div className="flex items-center gap-2">
        <span aria-hidden="true">{config.emoji}</span>
        <span className={`text-sm font-semibold capitalize ${config.text}`}>{label}</span>
        <span className={`text-xs ${config.text} opacity-60`}>
          {Math.round(confidence * 100)}%
        </span>
      </div>
      {toneDescription && (
        <p className={`text-xs ${config.text} opacity-80`}>{toneDescription}</p>
      )}
    </div>
  );
}
