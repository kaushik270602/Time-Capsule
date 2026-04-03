"use client";

import React, { useRef, useState, useCallback } from "react";

// Validation limits matching backend
const LIMITS: Record<string, { maxSize: number; formats: string[] }> = {
  video: { maxSize: 25 * 1024 * 1024, formats: ["video/mp4", "video/quicktime", "video/x-msvideo"] },
  audio: { maxSize: 25 * 1024 * 1024, formats: ["audio/mpeg", "audio/wav", "audio/x-m4a", "audio/mp4"] },
  image: { maxSize: 10 * 1024 * 1024, formats: ["image/jpeg", "image/png", "image/gif"] },
};

const ACCEPT_MAP: Record<string, string> = {
  video: ".mp4,.mov,.avi",
  audio: ".mp3,.wav,.m4a",
  image: ".jpg,.jpeg,.png,.gif",
};

const LABELS: Record<string, string> = {
  video: "Video",
  audio: "Audio",
  image: "Images",
};

export interface PendingFile {
  file: File;
  preview: string | null;
  mediaType: string;
  error?: string;
}

interface MediaUploaderProps {
  mediaType: "video" | "audio" | "image";
  files: PendingFile[];
  onChange: (files: PendingFile[]) => void;
  multiple?: boolean;
  maxFiles?: number;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(file: File, mediaType: string): string | undefined {
  const limit = LIMITS[mediaType];
  if (!limit) return "Unknown media type";
  if (!limit.formats.includes(file.type)) {
    return `Unsupported format. Allowed: ${ACCEPT_MAP[mediaType]}`;
  }
  if (file.size > limit.maxSize) {
    return `File too large. Max: ${formatSize(limit.maxSize)}`;
  }
  return undefined;
}

export default function MediaUploader({
  mediaType,
  files,
  onChange,
  multiple = false,
  maxFiles = 20,
}: MediaUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const addFiles = useCallback(
    (incoming: FileList | File[]) => {
      const arr = Array.from(incoming);
      const newPending: PendingFile[] = arr.map((f) => {
        const error = validateFile(f, mediaType);
        const preview =
          mediaType === "image" && !error ? URL.createObjectURL(f) : null;
        return { file: f, preview, mediaType, error };
      });

      if (multiple) {
        const merged = [...files, ...newPending].slice(0, maxFiles);
        onChange(merged);
      } else {
        onChange(newPending.slice(0, 1));
      }
    },
    [files, mediaType, multiple, maxFiles, onChange]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const removeFile = (idx: number) => {
    const updated = files.filter((_, i) => i !== idx);
    onChange(updated);
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-stone-700">
        {LABELS[mediaType]} {multiple ? `(max ${maxFiles})` : ""}
      </label>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label={`Upload ${LABELS[mediaType]}`}
        className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
          dragOver
            ? "border-amber-500 bg-amber-50"
            : "border-stone-300 hover:border-amber-400"
        }`}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <p className="text-sm text-stone-500">
          Drag & drop or click to select {LABELS[mediaType].toLowerCase()} files
        </p>
        <p className="text-xs text-stone-400 mt-1">
          Formats: {ACCEPT_MAP[mediaType]} &middot; Max: {formatSize(LIMITS[mediaType].maxSize)}
          {mediaType !== "image" && " (for AI transcription)"}
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept={ACCEPT_MAP[mediaType]}
        multiple={multiple}
        onChange={(e) => {
          if (e.target.files?.length) addFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {/* File list */}
      {files.length > 0 && (
        <ul className="space-y-2" aria-label={`Selected ${LABELS[mediaType]} files`}>
          {files.map((pf, idx) => (
            <li
              key={`${pf.file.name}-${idx}`}
              className="flex items-center gap-3 bg-stone-50 rounded-lg p-2"
            >
              {pf.preview && (
                <img
                  src={pf.preview}
                  alt={pf.file.name}
                  className="w-10 h-10 object-cover rounded"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{pf.file.name}</p>
                <p className="text-xs text-stone-400">{formatSize(pf.file.size)}</p>
                {pf.error && (
                  <p className="text-xs text-red-600" role="alert">
                    {pf.error}
                  </p>
                )}
              </div>
              <button
                type="button"
                aria-label={`Remove ${pf.file.name}`}
                className="text-stone-400 hover:text-red-500 text-lg"
                onClick={() => removeFile(idx)}
              >
                &times;
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
