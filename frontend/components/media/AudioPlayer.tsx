"use client";

import React, { useState } from "react";

export interface AudioPlayerProps {
  src: string;
  transcription?: string | null;
}

export default function AudioPlayer({ src, transcription }: AudioPlayerProps) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  if (hasError) {
    return (
      <div className="space-y-2">
        <div className="w-full rounded-lg bg-gray-100 border border-gray-200 flex flex-col items-center justify-center py-8 px-4 text-center">
          <span className="text-2xl mb-2" aria-hidden="true">⚠️</span>
          <p className="text-sm font-medium text-gray-700">Unable to load audio</p>
          <a
            href={src}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 text-sm text-indigo-600 hover:underline"
          >
            Download audio file
          </a>
        </div>
        {transcription && <Transcription text={transcription} />}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        {isLoading && (
          <div className="flex items-center justify-center bg-gray-100 rounded-lg py-6">
            <div className="animate-pulse text-gray-400 text-sm">Loading audio…</div>
          </div>
        )}
        <div className={`bg-gray-50 border border-gray-200 rounded-lg p-4 ${isLoading ? "hidden" : ""}`}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg" aria-hidden="true">🎵</span>
            <span className="text-sm font-medium text-gray-700">Audio</span>
          </div>
          <audio
            src={src}
            controls
            preload="metadata"
            className="w-full"
            onLoadedData={() => setIsLoading(false)}
            onError={() => {
              setIsLoading(false);
              setHasError(true);
            }}
          >
            Your browser does not support the audio element.
          </audio>
        </div>
      </div>
      {transcription && <Transcription text={transcription} />}
    </div>
  );
}

function Transcription({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > 300;

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-sm" aria-hidden="true">📝</span>
          <h3 className="text-sm font-medium text-gray-700">Transcription</h3>
        </div>
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-indigo-600 hover:underline"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
      </div>
      <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
        {isLong && !expanded ? text.slice(0, 300) + "…" : text}
      </p>
    </div>
  );
}
