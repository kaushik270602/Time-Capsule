"use client";

import React, { useState, useEffect, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { capsuleApi } from "@/lib/api";
import MediaUploader, { PendingFile } from "./MediaUploader";
import TimezoneSelector from "./TimezoneSelector";
import { detectBrowserTimezone } from "@/lib/timezone";

interface FormErrors {
  title?: string;
  unlock_date?: string;
  timezone?: string;
  submit?: string;
}

export default function CapsuleForm() {
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [textContent, setTextContent] = useState("");
  const [unlockDate, setUnlockDate] = useState("");
  const [timezone, setTimezone] = useState("");
  const [isPublic, setIsPublic] = useState(false);

  const [videoFiles, setVideoFiles] = useState<PendingFile[]>([]);
  const [audioFiles, setAudioFiles] = useState<PendingFile[]>([]);
  const [imageFiles, setImageFiles] = useState<PendingFile[]>([]);

  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});

  // Initialize timezone on mount
  useEffect(() => {
    if (!timezone) {
      setTimezone(detectBrowserTimezone());
    }
  }, [timezone]);

  // Minimum datetime for the picker (now + 1 minute)
  const minDate = () => {
    const d = new Date(Date.now() + 60_000);
    return d.toISOString().slice(0, 16);
  };

  function validate(): FormErrors {
    const errs: FormErrors = {};
    if (!title.trim()) errs.title = "Title is required";
    if (!unlockDate) {
      errs.unlock_date = "Unlock date is required";
    } else if (new Date(unlockDate) <= new Date()) {
      errs.unlock_date = "Unlock date must be in the future";
    }
    if (!timezone) {
      errs.timezone = "Timezone is required";
    }
    return errs;
  }

  // Check if any pending file has a validation error
  const allFiles = [...videoFiles, ...audioFiles, ...imageFiles];
  const hasFileErrors = allFiles.some((f) => !!f.error);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0 || hasFileErrors) return;

    setSubmitting(true);
    setErrors({});
    setUploadProgress({});

    try {
      // 1. Create capsule with timezone
      // Send the raw local datetime — the backend handles timezone conversion to UTC.
      // Do NOT convert to ISO/UTC here, as that would use the browser's timezone
      // and cause a double-conversion on the backend.
      const { data: capsule } = await capsuleApi.create({
        title: title.trim(),
        text_content: textContent.trim() || undefined,
        unlock_date: unlockDate,
        timezone: timezone,
        is_public: isPublic,
      });

      // 2. Upload media files sequentially
      const filesToUpload = allFiles.filter((f) => !f.error);
      for (let i = 0; i < filesToUpload.length; i++) {
        const pf = filesToUpload[i];
        const key = `${pf.file.name}-${i}`;
        try {
          await capsuleApi.uploadMedia(capsule.id, pf.file, (pct) => {
            setUploadProgress((prev) => ({ ...prev, [key]: pct }));
          });
          setUploadProgress((prev) => ({ ...prev, [key]: 100 }));
        } catch {
          setErrors({ submit: `Failed to upload ${pf.file.name}` });
          setSubmitting(false);
          return;
        }
      }

      // 3. Navigate to dashboard on success
      router.push("/dashboard");
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      // Handle timezone validation errors from API
      if (typeof detail === "string" && detail.toLowerCase().includes("timezone")) {
        setErrors({ timezone: detail });
      } else {
        const msg = detail || "Failed to create capsule. Please try again.";
        setErrors({ submit: msg });
      }
    } finally {
      setSubmitting(false);
    }
  }

  // Overall upload progress
  const filesToUpload = allFiles.filter((f) => !f.error);
  const totalUploads = filesToUpload.length;
  const completedUploads = Object.values(uploadProgress).filter((v) => v === 100).length;

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      {/* Title */}
      <div>
        <label htmlFor="title" className="block text-sm font-medium text-stone-700 mb-1">
          Title <span className="text-red-500">*</span>
        </label>
        <input
          id="title"
          type="text"
          maxLength={255}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${
            errors.title ? "border-red-500" : "border-stone-300"
          }`}
          aria-invalid={!!errors.title}
          aria-describedby={errors.title ? "title-error" : undefined}
          placeholder="Give your time capsule a name"
        />
        {errors.title && (
          <p id="title-error" className="mt-1 text-sm text-red-600" role="alert">
            {errors.title}
          </p>
        )}
      </div>

      {/* Text content */}
      <div>
        <label htmlFor="text-content" className="block text-sm font-medium text-stone-700 mb-1">
          Message
        </label>
        <textarea
          id="text-content"
          rows={5}
          value={textContent}
          onChange={(e) => setTextContent(e.target.value)}
          className="w-full px-3 py-2 border border-stone-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
          placeholder="Write a message to your future self..."
        />
      </div>

      {/* Unlock date */}
      <div>
        <label htmlFor="unlock-date" className="block text-sm font-medium text-stone-700 mb-1">
          Unlock Date & Time <span className="text-red-500">*</span>
        </label>
        <input
          id="unlock-date"
          type="datetime-local"
          min={minDate()}
          value={unlockDate}
          onChange={(e) => setUnlockDate(e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 ${
            errors.unlock_date ? "border-red-500" : "border-stone-300"
          }`}
          aria-invalid={!!errors.unlock_date}
          aria-describedby={errors.unlock_date ? "unlock-date-error" : undefined}
        />
        {errors.unlock_date && (
          <p id="unlock-date-error" className="mt-1 text-sm text-red-600" role="alert">
            {errors.unlock_date}
          </p>
        )}
      </div>

      {/* Timezone selector - associated with unlock date */}
      <TimezoneSelector
        value={timezone}
        onChange={setTimezone}
        error={errors.timezone}
      />

      {/* Privacy toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={isPublic}
          aria-label="Make capsule public"
          onClick={() => setIsPublic(!isPublic)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            isPublic ? "bg-amber-500" : "bg-stone-300"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              isPublic ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
        <span className="text-sm text-stone-700">
          {isPublic ? "Public — visible to everyone after unlock" : "Private — only you can see it"}
        </span>
      </div>

      {/* Media uploaders */}
      <div className="space-y-4 border-t pt-4">
        <h3 className="text-sm font-medium text-stone-700">Attach Media (optional)</h3>
        <MediaUploader mediaType="video" files={videoFiles} onChange={setVideoFiles} />
        <MediaUploader mediaType="audio" files={audioFiles} onChange={setAudioFiles} />
        <MediaUploader
          mediaType="image"
          files={imageFiles}
          onChange={setImageFiles}
          multiple
          maxFiles={20}
        />
      </div>

      {/* Upload progress */}
      {submitting && totalUploads > 0 && (
        <div className="bg-amber-50 rounded-lg p-3">
          <p className="text-sm text-amber-700">
            Uploading media: {completedUploads} / {totalUploads} files
          </p>
          <div className="mt-1 h-2 bg-amber-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-500 transition-all"
              style={{
                width: `${totalUploads > 0 ? (completedUploads / totalUploads) * 100 : 0}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Submit error */}
      {errors.submit && (
        <p className="text-sm text-red-600" role="alert">
          {errors.submit}
        </p>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={submitting || hasFileErrors}
        className="w-full py-2.5 px-4 bg-amber-500 text-white rounded-lg font-medium hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Creating Capsule..." : "Create Time Capsule"}
      </button>
    </form>
  );
}
