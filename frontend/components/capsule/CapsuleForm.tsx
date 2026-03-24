"use client";

import React, { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { capsuleApi } from "@/lib/api";
import MediaUploader, { PendingFile } from "./MediaUploader";

interface FormErrors {
  title?: string;
  unlock_date?: string;
  submit?: string;
}

export default function CapsuleForm() {
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [textContent, setTextContent] = useState("");
  const [unlockDate, setUnlockDate] = useState("");
  const [isPublic, setIsPublic] = useState(false);

  const [videoFiles, setVideoFiles] = useState<PendingFile[]>([]);
  const [audioFiles, setAudioFiles] = useState<PendingFile[]>([]);
  const [imageFiles, setImageFiles] = useState<PendingFile[]>([]);

  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});

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
      // 1. Create capsule
      const { data: capsule } = await capsuleApi.create({
        title: title.trim(),
        text_content: textContent.trim() || undefined,
        unlock_date: new Date(unlockDate).toISOString(),
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
      const msg =
        err.response?.data?.detail || "Failed to create capsule. Please try again.";
      setErrors({ submit: msg });
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
        <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
          Title <span className="text-red-500">*</span>
        </label>
        <input
          id="title"
          type="text"
          maxLength={255}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 ${
            errors.title ? "border-red-500" : "border-gray-300"
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
        <label htmlFor="text-content" className="block text-sm font-medium text-gray-700 mb-1">
          Message
        </label>
        <textarea
          id="text-content"
          rows={5}
          value={textContent}
          onChange={(e) => setTextContent(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          placeholder="Write a message to your future self..."
        />
      </div>

      {/* Unlock date */}
      <div>
        <label htmlFor="unlock-date" className="block text-sm font-medium text-gray-700 mb-1">
          Unlock Date & Time <span className="text-red-500">*</span>
        </label>
        <input
          id="unlock-date"
          type="datetime-local"
          min={minDate()}
          value={unlockDate}
          onChange={(e) => setUnlockDate(e.target.value)}
          className={`w-full px-3 py-2 border rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 ${
            errors.unlock_date ? "border-red-500" : "border-gray-300"
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

      {/* Privacy toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={isPublic}
          aria-label="Make capsule public"
          onClick={() => setIsPublic(!isPublic)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            isPublic ? "bg-indigo-600" : "bg-gray-300"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              isPublic ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
        <span className="text-sm text-gray-700">
          {isPublic ? "Public — visible to everyone after unlock" : "Private — only you can see it"}
        </span>
      </div>

      {/* Media uploaders */}
      <div className="space-y-4 border-t pt-4">
        <h3 className="text-sm font-medium text-gray-700">Attach Media (optional)</h3>
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
        <div className="bg-indigo-50 rounded-lg p-3">
          <p className="text-sm text-indigo-700">
            Uploading media: {completedUploads} / {totalUploads} files
          </p>
          <div className="mt-1 h-2 bg-indigo-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-600 transition-all"
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
        className="w-full py-2.5 px-4 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? "Creating Capsule..." : "Create Time Capsule"}
      </button>
    </form>
  );
}
