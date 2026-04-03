# Implementation Plan: AI Memory Enrichment

## Overview

Fix the existing broken AI services (OpenAI v1.x migration, S3 download fix) and expand them with sentiment detection, image analysis, video processing, and a unified memory recap. Each task builds incrementally: data model first, then utility services, then individual AI services, then orchestration, then API, then frontend.

## Tasks

- [x] 1. Expand AIAnalysis database model and schemas
  - [x] 1.1 Add new fields to AIAnalysis SQLAlchemy model
    - Add `sentiment_label` (String(20), nullable), `sentiment_confidence` (Float, nullable), `tone_description` (Text, nullable), `image_analyses` (JSON, nullable), `video_summaries` (JSON, nullable), `recap_text` (Text, nullable), `processing_status` (String(20), default "pending", not null), `error_message` (Text, nullable) to `backend/app/models/ai_analysis.py`
    - Add CheckConstraint for `processing_status IN ('pending', 'processing', 'completed', 'failed')`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 1.2 Update Pydantic response schema for AIAnalysis
    - Update or create `AIAnalysisResponse` in `backend/app/schemas/capsule.py` with all new fields: `summary`, `sentiment_label`, `sentiment_confidence`, `tone_description`, `image_analyses`, `video_summaries`, `recap_text`, `processing_status`, `created_at`
    - Ensure `CapsuleResponse` schema includes the expanded `ai_analysis` field
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 1.3 Create database migration for new AIAnalysis fields
    - Add migration in `backend/app/migrate.py` to add the new columns to the `ai_analysis` table
    - _Requirements: 6.1_

  - [ ]* 1.4 Write property test for AIAnalysis model field completeness
    - **Property 8: AIAnalysis model field completeness**
    - **Validates: Requirements 6.1, 6.2**

  - [ ]* 1.5 Write property test for processing status invariant
    - **Property 9: Processing status invariant**
    - **Validates: Requirements 6.3**

- [x] 2. Implement MediaDownloader utility
  - [x] 2.1 Create MediaDownloader service
    - Create `backend/app/services/media_downloader.py` with `download_to_temp(media_url)` and `cleanup(temp_path)` methods
    - Use `StorageAdapter` to download from S3, write to `tempfile.NamedTemporaryFile`
    - Handle S3 errors gracefully, raise `MediaDownloadError` on failure
    - _Requirements: 2.1, 4.4_

  - [ ]* 2.2 Write property test for base64 encoding round-trip
    - **Property 6: Base64 encoding round-trip for images**
    - **Validates: Requirements 4.4**

- [x] 3. Fix TranscriptionService with S3 download
  - [x] 3.1 Rewrite TranscriptionService to use MediaDownloader
    - Modify `backend/app/services/transcription_service.py` to use `MediaDownloader.download_to_temp()` instead of `open(media_url, "rb")`
    - Ensure temp file cleanup in `finally` block
    - Keep existing retry logic with exponential backoff
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 3.2 Write property test for temporary file cleanup
    - **Property 3: Temporary file cleanup after transcription**
    - **Validates: Requirements 2.3**

- [x] 4. Fix SummaryGenerator with OpenAI v1.x SDK
  - [x] 4.1 Migrate SummaryGenerator to OpenAI v1.x client
    - Modify `backend/app/services/summary_generator.py`: replace `openai.ChatCompletion.create()` with `self.client.chat.completions.create()`, replace `openai.error.APIError` with `openai.APIError`, instantiate `OpenAI` client in `__init__`
    - Keep temporal context in prompt and 200-word limit instruction
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 4.2 Write property test for summary temporal context
    - **Property 1: Summary prompt includes temporal context**
    - **Validates: Requirements 1.2**

  - [ ]* 4.3 Write property test for summary word count limit
    - **Property 2: Summary word count limit**
    - **Validates: Requirements 1.3**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement SentimentDetector service
  - [x] 6.1 Create SentimentDetector service
    - Create `backend/app/services/sentiment_detector.py` with `detect_sentiment(text)` method
    - Use `client.chat.completions.create()` with a prompt requesting JSON output with `label`, `confidence`, `tone_description`
    - Validate `label` against `VALID_LABELS` list, return default `{"label": "neutral", "confidence": 0.0, "tone_description": ""}` on failure
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 6.2 Write property test for sentiment detection output validity
    - **Property 4: Sentiment detection output validity**
    - **Validates: Requirements 3.1, 3.2, 3.3**

- [x] 7. Implement VisionAnalyzer service
  - [x] 7.1 Create VisionAnalyzer service
    - Create `backend/app/services/vision_analyzer.py` with `analyze_image(media_url)` and `analyze_images(media_urls)` methods
    - Use `MediaDownloader` to download image, encode as base64, send to GPT-4o via `client.chat.completions.create()` with image content
    - Return `{"media_url": str, "caption": str, "tags": list}` per image
    - Skip failures in `analyze_images()`, return partial results
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 7.2 Write property test for image analysis output format
    - **Property 5: Image analysis output format**
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 7.3 Write property test for image analysis skips failures
    - **Property 7: Image analysis skips failures without blocking**
    - **Validates: Requirements 4.5**

- [x] 8. Implement RecapGenerator service
  - [x] 8.1 Create RecapGenerator service
    - Create `backend/app/services/recap_generator.py` with `generate_recap(summary, sentiment, image_analyses, video_summaries, created_at, unlocked_at)` method
    - Use `client.chat.completions.create()` with a prompt combining all available insights and temporal context
    - Return None if no insights are available
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 8.2 Write property test for recap incorporating available insights
    - **Property 11: Recap incorporates available insights with temporal context**
    - **Validates: Requirements 7.1, 7.3**

  - [ ]* 8.3 Write property test for recap word count range
    - **Property 12: Recap word count range**
    - **Validates: Requirements 7.2**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Rewrite AIService orchestrator
  - [x] 10.1 Rewrite AIService with full pipeline and error isolation
    - Rewrite `backend/app/services/ai_service.py` to instantiate all services: `TranscriptionService`, `SummaryGenerator`, `SentimentDetector`, `VisionAnalyzer`, `RecapGenerator`
    - Implement `analyze_capsule()` with the fixed pipeline order: transcription → sentiment → image analysis → summary → recap
    - Create AIAnalysis record upfront with `processing_status="pending"`, update to `"processing"`, then `"completed"`
    - Wrap each step in its own try/except for error isolation, save partial results after each step
    - Store video summaries in `video_summaries` JSON field (media_url, transcription, summary per video)
    - Only set `processing_status="failed"` on catastrophic errors (DB failure)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.4, 6.5, 6.6, 11.1, 11.2, 11.3, 11.4_

  - [ ]* 10.2 Write property test for pipeline execution order
    - **Property 14: Pipeline execution order**
    - **Validates: Requirements 11.1**

  - [ ]* 10.3 Write property test for pipeline error isolation
    - **Property 15: Pipeline error isolation**
    - **Validates: Requirements 11.2**

  - [ ]* 10.4 Write property test for processing status lifecycle
    - **Property 10: Processing status lifecycle**
    - **Validates: Requirements 6.4, 6.5**

- [x] 11. Update Celery task and unlock orchestrator
  - [x] 11.1 Update Celery analyze_capsule_task
    - Update `backend/app/tasks/ai_analysis.py` to include `processing_status` in the return dict
    - Ensure retry logic aligns with design (max 3 retries, exponential backoff)
    - _Requirements: 11.5_

  - [x] 11.2 Verify unlock orchestrator triggers AI analysis
    - Confirm `backend/app/services/unlock_orchestrator.py` `_trigger_ai_analysis` correctly dispatches the Celery task (already wired, verify no changes needed)
    - _Requirements: 11.5_

- [x] 12. Update capsule API endpoint to return full AI analysis
  - [x] 12.1 Update GET /api/capsules/{id} response to include expanded ai_analysis
    - Modify `backend/app/routers/capsules.py` `get_capsule` endpoint and `CapsuleService.get_capsule()` to serialize the full AIAnalysis fields in the response
    - Return `ai_analysis: null` when no AIAnalysis record exists
    - Return `processing_status` for pending/processing states
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 12.2 Write property test for API response completeness
    - **Property 13: API response completeness for unlocked capsules**
    - **Validates: Requirements 8.1, 8.2, 8.3**

- [x] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Update frontend TypeScript types
  - [x] 14.1 Expand AIAnalysisResponse and add new interfaces in frontend/lib/api.ts
    - Add `ImageAnalysis` interface (`media_url`, `caption`, `tags`)
    - Add `VideoSummary` interface (`media_url`, `transcription`, `summary`)
    - Expand `AIAnalysisResponse` with all new fields: `sentiment_label`, `sentiment_confidence`, `tone_description`, `image_analyses`, `video_summaries`, `recap_text`, `processing_status`
    - _Requirements: 10.1, 10.2_

- [x] 15. Implement frontend AI enrichment components
  - [x] 15.1 Create SentimentBadge component
    - Create `frontend/components/capsule/SentimentBadge.tsx` with emoji and color mapping per sentiment label, pill-shaped badge with tone description tooltip
    - _Requirements: 9.3_

  - [x] 15.2 Create AIProcessingIndicator component
    - Create `frontend/components/capsule/AIProcessingIndicator.tsx` with animated loading state for "pending"/"processing" and subtle error notice for "failed"
    - _Requirements: 9.6, 9.7_

  - [x] 15.3 Create MemoryRecapView component
    - Create `frontend/components/capsule/MemoryRecapView.tsx` with gradient card displaying recap text and optional sentiment badge
    - _Requirements: 9.1, 9.2_

  - [x] 15.4 Update CapsuleDetailPage to display all AI enrichment
    - Modify `frontend/app/capsules/[id]/page.tsx` to:
      - Show `AIProcessingIndicator` when status is "pending" or "processing"
      - Show `MemoryRecapView` as first section when `recap_text` is available
      - Show `SentimentBadge` when `sentiment_label` is available
      - Show AI captions and tags below each image using `image_analyses`
      - Show AI summaries below each video using `video_summaries`
      - Show subtle notice when `processing_status` is "failed"
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

- [x] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- The design uses Python (backend) and TypeScript (frontend) directly, no language selection needed
- Existing property test files at `backend/tests/property/test_ai_properties.py` and `backend/tests/property/test_transcription_properties.py` should be extended
