"use client";

import React from "react";

interface StatsCardsProps {
  total: number;
  locked: number;
  unlocked: number;
  loading?: boolean;
}

export default function StatsCards({ total, locked, unlocked, loading }: StatsCardsProps) {
  const cards = [
    { label: "Total Capsules", value: total, color: "bg-amber-50 text-amber-700", icon: "📦" },
    { label: "Locked", value: locked, color: "bg-orange-50 text-orange-700", icon: "🔒" },
    { label: "Unlocked", value: unlocked, color: "bg-emerald-50 text-emerald-700", icon: "🔓" },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-white rounded-xl border border-stone-200 p-6 shadow-sm"
        >
          <div className="flex items-center gap-3 mb-2">
            <span
              className={`inline-flex items-center justify-center w-10 h-10 rounded-lg text-lg ${card.color}`}
              aria-hidden="true"
            >
              {card.icon}
            </span>
            <span className="text-sm font-medium text-stone-600">{card.label}</span>
          </div>
          <div className="text-3xl font-bold text-stone-900">
            {loading ? (
              <span className="inline-block w-12 h-8 bg-stone-200 rounded animate-pulse" />
            ) : (
              card.value
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
