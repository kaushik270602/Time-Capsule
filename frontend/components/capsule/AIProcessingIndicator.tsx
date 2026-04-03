"use client";

import React from "react";

interface AIProcessingIndicatorProps {
  status: "pending" | "processing" | "completed" | "failed";
}

export default function AIProcessingIndicator({ status }: AIProcessingIndicatorProps) {
  if (status === "completed") return null;

  if (status === "failed") {
    return (
      <div className="bg-stone-50 border border-stone-200 rounded-xl p-4 text-center">
        <p className="text-sm text-stone-500">
          AI analysis was unavailable for this capsule. Showing original content.
        </p>
      </div>
    );
  }

  // pending or processing
  return (
    <div className="bg-violet-50 border border-violet-200 rounded-xl p-6 text-center space-y-3">
      <div className="flex justify-center">
        <div className="animate-spin h-8 w-8 border-4 border-violet-300 border-t-violet-600 rounded-full" role="status">
          <span className="sr-only">Loading</span>
        </div>
      </div>
      <p className="text-sm text-violet-700 font-medium">
        AI is analyzing your memories...
      </p>
    </div>
  );
}
