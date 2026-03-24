"use client";

import React, { useState, useCallback, useEffect } from "react";

export interface ImageGalleryProps {
  images: { src: string; alt?: string }[];
}

export default function ImageGallery({ images }: ImageGalleryProps) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [loadErrors, setLoadErrors] = useState<Set<number>>(new Set());
  const [loadingSet, setLoadingSet] = useState<Set<number>>(
    () => new Set(images.map((_, i) => i))
  );

  const openLightbox = (index: number) => setLightboxIndex(index);
  const closeLightbox = () => setLightboxIndex(null);

  const goNext = useCallback(() => {
    if (lightboxIndex === null) return;
    setLightboxIndex((lightboxIndex + 1) % images.length);
  }, [lightboxIndex, images.length]);

  const goPrev = useCallback(() => {
    if (lightboxIndex === null) return;
    setLightboxIndex((lightboxIndex - 1 + images.length) % images.length);
  }, [lightboxIndex, images.length]);

  useEffect(() => {
    if (lightboxIndex === null) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowRight") goNext();
      if (e.key === "ArrowLeft") goPrev();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [lightboxIndex, goNext, goPrev]);

  const handleImageLoad = (index: number) => {
    setLoadingSet((prev) => {
      const next = new Set(prev);
      next.delete(index);
      return next;
    });
  };

  const handleImageError = (index: number) => {
    setLoadErrors((prev) => new Set(prev).add(index));
    handleImageLoad(index);
  };

  if (images.length === 0) return null;

  return (
    <>
      {/* Grid */}
      <div
        className={`grid gap-3 ${
          images.length === 1
            ? "grid-cols-1"
            : images.length === 2
            ? "grid-cols-2"
            : "grid-cols-2 sm:grid-cols-3"
        }`}
      >
        {images.map((img, index) => (
          <div key={index} className="relative group">
            {loadingSet.has(index) && !loadErrors.has(index) && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg">
                <div className="animate-pulse text-gray-400 text-sm">Loading…</div>
              </div>
            )}
            {loadErrors.has(index) ? (
              <div className="w-full aspect-square rounded-lg bg-gray-100 border border-gray-200 flex flex-col items-center justify-center text-center p-4">
                <span className="text-2xl mb-1" aria-hidden="true">🖼️</span>
                <p className="text-xs text-gray-500">Failed to load</p>
              </div>
            ) : (
              <button
                onClick={() => openLightbox(index)}
                className="w-full focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded-lg"
                aria-label={img.alt || `View image ${index + 1}`}
              >
                <img
                  src={img.src}
                  alt={img.alt || `Image ${index + 1}`}
                  className="w-full aspect-square object-cover rounded-lg hover:opacity-90 transition-opacity cursor-pointer"
                  onLoad={() => handleImageLoad(index)}
                  onError={() => handleImageError(index)}
                />
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Lightbox */}
      {lightboxIndex !== null && !loadErrors.has(lightboxIndex) && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={closeLightbox}
          role="dialog"
          aria-modal="true"
          aria-label="Image lightbox"
        >
          <div
            className="relative max-w-5xl max-h-[90vh] w-full flex items-center justify-center"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              onClick={closeLightbox}
              className="absolute top-2 right-2 z-10 bg-black/50 hover:bg-black/70 text-white rounded-full w-10 h-10 flex items-center justify-center transition-colors"
              aria-label="Close lightbox"
            >
              ✕
            </button>

            {/* Previous */}
            {images.length > 1 && (
              <button
                onClick={goPrev}
                className="absolute left-2 z-10 bg-black/50 hover:bg-black/70 text-white rounded-full w-10 h-10 flex items-center justify-center transition-colors"
                aria-label="Previous image"
              >
                ‹
              </button>
            )}

            {/* Image */}
            <img
              src={images[lightboxIndex].src}
              alt={images[lightboxIndex].alt || `Image ${lightboxIndex + 1}`}
              className="max-w-full max-h-[85vh] object-contain rounded-lg"
            />

            {/* Next */}
            {images.length > 1 && (
              <button
                onClick={goNext}
                className="absolute right-2 z-10 bg-black/50 hover:bg-black/70 text-white rounded-full w-10 h-10 flex items-center justify-center transition-colors"
                aria-label="Next image"
              >
                ›
              </button>
            )}

            {/* Counter */}
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/50 text-white text-sm px-3 py-1 rounded-full">
              {lightboxIndex + 1} / {images.length}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
