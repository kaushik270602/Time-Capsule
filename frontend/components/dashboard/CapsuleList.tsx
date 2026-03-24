"use client";

import React from "react";
import { CapsuleResponse } from "@/lib/api";
import CapsuleCard from "./CapsuleCard";

interface CapsuleListProps {
  capsules: CapsuleResponse[];
}

export default function CapsuleList({ capsules }: CapsuleListProps) {
  const locked = capsules.filter((c) => c.status === "locked");
  const unlocked = capsules.filter((c) => c.status === "unlocked");

  if (capsules.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
        <p className="text-gray-500 mb-4">You haven&apos;t created any capsules yet.</p>
        <a
          href="/capsules/new"
          className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
        >
          Create Your First Capsule
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {locked.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <span aria-hidden="true">🔒</span>
            Locked Capsules
            <span className="text-sm font-normal text-gray-500">({locked.length})</span>
          </h2>
          <div className="space-y-3">
            {locked.map((capsule) => (
              <CapsuleCard key={capsule.id} capsule={capsule} />
            ))}
          </div>
        </section>
      )}

      {unlocked.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <span aria-hidden="true">🔓</span>
            Unlocked Capsules
            <span className="text-sm font-normal text-gray-500">({unlocked.length})</span>
          </h2>
          <div className="space-y-3">
            {unlocked.map((capsule) => (
              <CapsuleCard key={capsule.id} capsule={capsule} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
