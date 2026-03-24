"use client";

import React, { useState, useRef } from "react";

export interface VideoPlayerProps {
  src: string;
  transcription?: string | null;
}

export default function VideoPlayer({ src, transcription }: VideoPlayerProps) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const videoRef = useRef<HTMLVideoElement>(null);

  if (hasError) {
    return (
      <div className="space-y-2">
        <div className="w-full rounded-lg bg-gray-100 border border-gray-200 flex flex-col items-center justify-center py-12 px-4 text-center">
          <span className="text-3xl mb-2" aria-hidden="true">⚠️</span>
          <p className="text-sm font-medium text-gray-700">Unable to load video</p>
          <a
            href={src}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 text-sm text-indigo-600 hover:underline"
          >
            Download video file
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
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg">
            <div className="animate-pulse text-gray-400 text-sm">Loading video…</div>
          </div>
        )}
        <video
          ref={videoRef}
          src={src}
          controls
          preload="metadata"
          className="w-full rounded-lg bg-black max-h-[480px]"
          onLoadedData={() => setIsLoading(false)}
          onError={() => {
            setIsLoading(false);
            setHasError(true);
          }}
        >
          Your browser does not support the video element.
        </video>
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
