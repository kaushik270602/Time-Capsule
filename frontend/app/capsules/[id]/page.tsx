"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { capsuleApi, CapsuleResponse } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import VideoPlayer from "@/components/media/VideoPlayer";
import AudioPlayer from "@/components/media/AudioPlayer";
import ImageGallery from "@/components/media/ImageGallery";

function computeCountdown(unlockDate: string): string {
  const now = Date.now();
  const target = new Date(unlockDate).getTime();
  const diff = target - now;
  if (diff <= 0) return "Unlocking soon…";

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
  const seconds = Math.floor((diff % (1000 * 60)) / 1000);

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);
  return parts.join(" ");
}

function getMediaType(url: string): "video" | "audio" | "image" | "unknown" {
  const lower = url.toLowerCase();
  if (/\.(mp4|mov|avi|webm)(\?|$)/.test(lower)) return "video";
  if (/\.(mp3|wav|m4a|ogg)(\?|$)/.test(lower)) return "audio";
  if (/\.(jpg|jpeg|png|gif|webp|svg)(\?|$)/.test(lower)) return "image";
  return "unknown";
}

export default function CapsuleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [capsule, setCapsule] = useState<CapsuleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState("");

  const capsuleId = Number(params.id);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/login");
      return;
    }

    const fetchCapsule = async () => {
      try {
        const { data } = await capsuleApi.get(capsuleId);
        setCapsule(data);
      } catch (err: any) {
        const status = err.response?.status;
        if (status === 404) setError("Capsule not found.");
        else if (status === 403) setError("You don't have access to this capsule.");
        else setError("Failed to load capsule.");
      } finally {
        setLoading(false);
      }
    };

    fetchCapsule();
  }, [capsuleId, user, authLoading, router]);

  const isLocked = capsule?.status === "locked";

  useEffect(() => {
    if (!capsule || !isLocked) return;
    setCountdown(computeCountdown(capsule.unlock_date));
    const id = setInterval(() => {
      setCountdown(computeCountdown(capsule.unlock_date));
    }, 1000);
    return () => clearInterval(id);
  }, [capsule, isLocked]);

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-pulse text-gray-400">Loading capsule…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center gap-4">
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-6 max-w-md text-center">
          <p className="font-medium">{error}</p>
        </div>
        <Link href="/dashboard" className="text-indigo-600 hover:underline text-sm">
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  if (!capsule) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-indigo-600">
            TimeLock
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/dashboard" className="text-gray-600 hover:text-gray-900">
              Dashboard
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* Back link */}
        <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          ← Back to Dashboard
        </Link>

        {/* Title & status header */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div className="flex items-center gap-3">
              <span
                className={`flex-shrink-0 inline-flex items-center justify-center w-12 h-12 rounded-lg text-xl ${
                  isLocked ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"
                }`}
                aria-hidden="true"
              >
                {isLocked ? "🔒" : "🔓"}
              </span>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{capsule.title}</h1>
                <p className="text-sm text-gray-500 mt-1">
                  Created {new Date(capsule.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {capsule.is_public ? (
                <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-blue-100 text-blue-700">
                  Public
                </span>
              ) : (
                <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">
                  Private
                </span>
              )}
              <span
                className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                  isLocked ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"
                }`}
              >
                {capsule.status}
              </span>
            </div>
          </div>
        </div>

        {/* Locked state */}
        {isLocked && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center space-y-4">
            <div className="text-4xl" aria-hidden="true">🔒</div>
            <h2 className="text-lg font-semibold text-amber-800">This capsule is locked</h2>
            <p className="text-sm text-amber-700">
              Content will be revealed on{" "}
              <span className="font-medium">
                {new Date(capsule.unlock_date).toLocaleString()}
              </span>
            </p>
            {countdown && (
              <div className="inline-flex items-center gap-2 bg-amber-100 rounded-lg px-4 py-2 text-amber-800">
                <span aria-hidden="true">⏳</span>
                <span className="font-mono text-lg font-semibold">{countdown}</span>
              </div>
            )}
          </div>
        )}

        {/* Unlocked content */}
        {!isLocked && (
          <>
            {/* AI Summary */}
            {capsule.ai_analysis?.summary && (
              <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-lg" aria-hidden="true">✨</span>
                  <h2 className="text-lg font-semibold text-indigo-900">AI Summary</h2>
                </div>
                <p className="text-indigo-800 leading-relaxed whitespace-pre-wrap">
                  {capsule.ai_analysis.summary}
                </p>
              </div>
            )}

            {/* Text content */}
            {capsule.text_content && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-3">Message</h2>
                <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {capsule.text_content}
                </p>
              </div>
            )}

            {/* Media files */}
            {capsule.media_urls.length > 0 && (() => {
              const videos: { url: string; transcription: string | null }[] = [];
              const audios: { url: string; transcription: string | null }[] = [];
              const imageList: { src: string; alt?: string }[] = [];
              const unknowns: { url: string; index: number }[] = [];

              capsule.media_urls.forEach((url, index) => {
                const type = getMediaType(url);
                const transcription = capsule.transcriptions?.[index] ?? null;
                if (type === "video") videos.push({ url, transcription });
                else if (type === "audio") audios.push({ url, transcription });
                else if (type === "image") imageList.push({ src: url, alt: `Image ${index + 1}` });
                else unknowns.push({ url, index });
              });

              return (
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
                  <h2 className="text-lg font-semibold text-gray-900">Media</h2>

                  {/* Videos */}
                  {videos.map((v, i) => (
                    <VideoPlayer key={`video-${i}`} src={v.url} transcription={v.transcription} />
                  ))}

                  {/* Audio */}
                  {audios.map((a, i) => (
                    <AudioPlayer key={`audio-${i}`} src={a.url} transcription={a.transcription} />
                  ))}

                  {/* Images */}
                  {imageList.length > 0 && <ImageGallery images={imageList} />}

                  {/* Unknown files */}
                  {unknowns.map((u) => (
                    <a
                      key={`unknown-${u.index}`}
                      href={u.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:underline text-sm block"
                    >
                      Download media file {u.index + 1}
                    </a>
                  ))}
                </div>
              );
            })()}

            {/* Unlock info */}
            <div className="text-center text-sm text-gray-400 py-4">
              Unlocked on {new Date(capsule.unlock_date).toLocaleString()}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
