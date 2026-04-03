"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { capsuleApi, CapsuleResponse, ImageAnalysis, VideoSummary } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { formatUnlockDate } from "@/lib/timezone";
import VideoPlayer from "@/components/media/VideoPlayer";
import AudioPlayer from "@/components/media/AudioPlayer";
import ImageGallery from "@/components/media/ImageGallery";
import MemoryRecapView from "@/components/capsule/MemoryRecapView";
import SentimentBadge from "@/components/capsule/SentimentBadge";
import AIProcessingIndicator from "@/components/capsule/AIProcessingIndicator";

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
  const [analyzing, setAnalyzing] = useState(false);

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
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <div className="animate-pulse text-stone-400">Loading capsule…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-stone-50 flex flex-col items-center justify-center gap-4">
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-6 max-w-md text-center">
          <p className="font-medium">{error}</p>
        </div>
        <Link href="/dashboard" className="text-amber-600 hover:underline text-sm">
          ← Back to Dashboard
        </Link>
      </div>
    );
  }

  if (!capsule) return null;

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-amber-500">
            TimeLock
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/dashboard" className="text-stone-600 hover:text-stone-900">
              Dashboard
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* Back link */}
        <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm text-stone-500 hover:text-stone-700">
          ← Back to Dashboard
        </Link>

        {/* Title & status header */}
        <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6">
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
                <h1 className="text-2xl font-bold text-stone-900">{capsule.title}</h1>
                <p className="text-sm text-stone-500 mt-1">
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
                <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-stone-100 text-stone-600">
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
                {formatUnlockDate(capsule.unlock_date, capsule.timezone || 'UTC')}
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
            {/* No AI analysis yet — offer to trigger it */}
            {!capsule.ai_analysis && (
              <div className="bg-violet-50 border border-violet-200 rounded-xl p-6 text-center space-y-3">
                <span className="text-2xl" aria-hidden="true">✨</span>
                <p className="text-sm text-violet-700">AI hasn't analyzed this memory yet.</p>
                <button
                  onClick={async () => {
                    setAnalyzing(true);
                    try {
                      await capsuleApi.triggerAnalysis(capsuleId);
                      // Refetch capsule to show processing status
                      const { data } = await capsuleApi.get(capsuleId);
                      setCapsule(data);
                    } catch {
                      // ignore — might already be analyzed
                    } finally {
                      setAnalyzing(false);
                    }
                  }}
                  disabled={analyzing}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500 text-white text-sm font-medium rounded-lg hover:bg-amber-600 disabled:opacity-50"
                >
                  {analyzing ? "Analyzing..." : "Analyze with AI"}
                </button>
              </div>
            )}

            {/* AI Processing Indicator */}
            {capsule.ai_analysis && capsule.ai_analysis.processing_status !== "completed" && (
              <AIProcessingIndicator status={capsule.ai_analysis.processing_status as "pending" | "processing" | "failed"} />
            )}

            {/* Memory Recap */}
            {capsule.ai_analysis?.recap_text && (
              <MemoryRecapView
                recapText={capsule.ai_analysis.recap_text}
                sentimentLabel={capsule.ai_analysis.sentiment_label}
                sentimentConfidence={capsule.ai_analysis.sentiment_confidence}
                toneDescription={capsule.ai_analysis.tone_description}
              />
            )}

            {/* Sentiment Badge (shown separately if no recap) */}
            {!capsule.ai_analysis?.recap_text && capsule.ai_analysis?.sentiment_label && (
              <SentimentBadge
                label={capsule.ai_analysis.sentiment_label}
                confidence={capsule.ai_analysis.sentiment_confidence ?? 0}
                toneDescription={capsule.ai_analysis.tone_description ?? ""}
              />
            )}

            {/* AI Summary */}
            {capsule.ai_analysis?.summary && (
              <div className="bg-violet-50 border border-violet-200 rounded-xl p-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-lg" aria-hidden="true">✨</span>
                  <h2 className="text-lg font-semibold text-violet-900">AI Summary</h2>
                </div>
                <p className="text-violet-800 leading-relaxed whitespace-pre-wrap">
                  {capsule.ai_analysis.summary}
                </p>
              </div>
            )}

            {/* Text content */}
            {capsule.text_content && (
              <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6">
                <h2 className="text-lg font-semibold text-stone-900 mb-3">Message</h2>
                <p className="text-stone-700 leading-relaxed whitespace-pre-wrap">
                  {capsule.text_content}
                </p>
              </div>
            )}

            {/* Media files */}
            {capsule.media_urls.length > 0 && (() => {
              const ai = capsule.ai_analysis;
              const videos: { url: string; transcription: string | null; aiSummary?: string }[] = [];
              const audios: { url: string; transcription: string | null }[] = [];
              const imageList: { src: string; alt?: string; caption?: string; tags?: string[] }[] = [];
              const unknowns: { url: string; index: number }[] = [];

              capsule.media_urls.forEach((url, index) => {
                const type = getMediaType(url);
                const transcription = capsule.transcriptions?.[index] ?? null;
                if (type === "video") {
                  const vidSummary = ai?.video_summaries?.find((v: VideoSummary) => v.media_url === url);
                  videos.push({ url, transcription, aiSummary: vidSummary?.summary });
                } else if (type === "audio") {
                  audios.push({ url, transcription });
                } else if (type === "image") {
                  const imgAnalysis = ai?.image_analyses?.find((img: ImageAnalysis) => img.media_url === url);
                  imageList.push({
                    src: url,
                    alt: imgAnalysis?.caption || `Image ${index + 1}`,
                    caption: imgAnalysis?.caption,
                    tags: imgAnalysis?.tags,
                  });
                } else {
                  unknowns.push({ url, index });
                }
              });

              return (
                <div className="bg-white rounded-xl shadow-sm border border-stone-200 p-6 space-y-6">
                  <h2 className="text-lg font-semibold text-stone-900">Media</h2>

                  {/* Videos with AI summaries */}
                  {videos.map((v, i) => (
                    <div key={`video-${i}`} className="space-y-2">
                      <VideoPlayer src={v.url} transcription={v.transcription} />
                      {v.aiSummary && (
                        <div className="bg-violet-50 rounded-lg p-3">
                          <p className="text-sm text-violet-800">
                            <span className="font-medium">AI Summary:</span> {v.aiSummary}
                          </p>
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Audio */}
                  {audios.map((a, i) => (
                    <AudioPlayer key={`audio-${i}`} src={a.url} transcription={a.transcription} />
                  ))}

                  {/* Images with AI captions and tags */}
                  {imageList.length > 0 && (
                    <div className="space-y-4">
                      <ImageGallery images={imageList.map(img => ({ src: img.src, alt: img.alt }))} />
                      {imageList.some(img => img.caption || img.tags?.length) && (
                        <div className="space-y-3">
                          {imageList.map((img, i) => (
                            (img.caption || img.tags?.length) ? (
                              <div key={`img-ai-${i}`} className="bg-stone-50 rounded-lg p-3">
                                {img.caption && (
                                  <p className="text-sm text-stone-700">{img.caption}</p>
                                )}
                                {img.tags && img.tags.length > 0 && (
                                  <div className="flex flex-wrap gap-1 mt-2">
                                    {img.tags.map((tag, ti) => (
                                      <span key={ti} className="text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">
                                        {tag}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ) : null
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Unknown files */}
                  {unknowns.map((u) => (
                    <a
                      key={`unknown-${u.index}`}
                      href={u.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-amber-600 hover:underline text-sm block"
                    >
                      Download media file {u.index + 1}
                    </a>
                  ))}
                </div>
              );
            })()}

            {/* Unlock info */}
            <div className="text-center text-sm text-stone-400 py-4">
              Unlocked on {formatUnlockDate(capsule.unlock_date, capsule.timezone || 'UTC')}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
