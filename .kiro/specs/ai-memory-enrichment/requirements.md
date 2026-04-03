# Requirements Document

## Introduction

The AI Memory Enrichment feature enhances the TimeLock time capsule application by applying AI analysis to all media types (text, audio, video, images) stored in capsules. At unlock time, the system generates rich AI insights including summaries, sentiment analysis, transcriptions, image descriptions, and a unified "memory recap" experience. This feature builds on existing scaffolded but non-functional AI code, fixing the broken text summarization and audio transcription, and adding new capabilities for sentiment detection, image analysis, video processing, and a cohesive recap presentation.

## Glossary

- **AI_Service**: The backend orchestrator service that coordinates all AI analysis operations on a capsule
- **Summary_Generator**: The service responsible for generating text summaries using the OpenAI Chat Completions API
- **Transcription_Service**: The service responsible for transcribing audio content using the OpenAI Whisper API
- **Vision_Analyzer**: The service responsible for analyzing images using the OpenAI Vision API (GPT-4o)
- **Sentiment_Detector**: The service responsible for detecting tone and sentiment in text content using the OpenAI Chat Completions API
- **Recap_Generator**: The service responsible for generating a unified memory recap that combines all AI insights for a capsule
- **AIAnalysis_Model**: The database model that stores all AI analysis results for a capsule, including summary, sentiment, image tags, transcriptions, and recap
- **Capsule_Detail_Page**: The frontend page that displays a single capsule's content and AI analysis results
- **Memory_Recap_View**: The frontend component that presents the AI-generated memory recap before showing original content
- **Media_Downloader**: The utility responsible for downloading media files from S3 to a temporary local path for AI processing
- **OpenAI_Client**: The OpenAI Python SDK client (v1.x) used for all API calls

## Requirements

### Requirement 1: Fix Text Summarization with Modern OpenAI SDK

**User Story:** As a capsule owner, I want my text capsule to be summarized by AI when it unlocks, so that I get a thoughtful reflection on my past message.

#### Acceptance Criteria

1. WHEN a capsule with text content is unlocked, THE Summary_Generator SHALL generate a summary using the OpenAI Chat Completions API via the OpenAI_Client v1.x `client.chat.completions.create()` method
2. THE Summary_Generator SHALL include temporal context (time elapsed between capsule creation and unlock) in the summary prompt
3. THE Summary_Generator SHALL limit the generated summary to 200 words
4. IF the OpenAI API returns an error, THEN THE Summary_Generator SHALL retry up to 3 times with exponential backoff (1s, 2s, 4s delays)
5. IF all retry attempts fail, THEN THE Summary_Generator SHALL return None and log the error without blocking capsule access
6. THE Summary_Generator SHALL store the generated summary in the AIAnalysis_Model `summary` field

### Requirement 2: Fix Audio Transcription with S3 Media Download

**User Story:** As a capsule owner, I want audio messages in my capsule to be transcribed when it unlocks, so that I can read what was said.

#### Acceptance Criteria

1. WHEN a capsule with audio media files (.mp3, .wav, .m4a) is unlocked, THE Transcription_Service SHALL download the audio file from S3 using the Media_Downloader to a temporary local path
2. THE Transcription_Service SHALL transcribe the downloaded audio file using the OpenAI Whisper API via `client.audio.transcriptions.create()`
3. THE Transcription_Service SHALL delete the temporary file after transcription completes or fails
4. IF the OpenAI Whisper API returns an error, THEN THE Transcription_Service SHALL retry up to 3 times with exponential backoff
5. IF all retry attempts fail, THEN THE Transcription_Service SHALL return None and log the error without blocking capsule access
6. THE AI_Service SHALL store transcription results in the Capsule `transcriptions` JSON field

### Requirement 3: Sentiment and Tone Detection for Text

**User Story:** As a capsule owner, I want to see the emotional tone of my past message, so that I can reflect on how I was feeling when I wrote it.

#### Acceptance Criteria

1. WHEN a capsule with text content is unlocked, THE Sentiment_Detector SHALL analyze the text and return a sentiment label (one of: "joyful", "nostalgic", "hopeful", "reflective", "anxious", "sad", "excited", "neutral")
2. THE Sentiment_Detector SHALL also return a confidence score between 0.0 and 1.0
3. THE Sentiment_Detector SHALL also return a one-sentence tone description (e.g., "This message carries a hopeful and optimistic tone about the future")
4. THE Sentiment_Detector SHALL use the OpenAI Chat Completions API with a structured JSON response format
5. IF the OpenAI API returns an error, THEN THE Sentiment_Detector SHALL return a default sentiment of "neutral" with confidence 0.0
6. THE AI_Service SHALL store sentiment results in the AIAnalysis_Model `sentiment_label`, `sentiment_confidence`, and `tone_description` fields

### Requirement 4: Image Tagging and Captioning

**User Story:** As a capsule owner, I want AI-generated descriptions of my photos, so that my visual memories are enriched with context.

#### Acceptance Criteria

1. WHEN a capsule with image media files (.jpg, .jpeg, .png, .gif, .webp) is unlocked, THE Vision_Analyzer SHALL analyze each image using the OpenAI Vision API (GPT-4o model with image input)
2. THE Vision_Analyzer SHALL generate a descriptive caption (1-2 sentences) for each image
3. THE Vision_Analyzer SHALL generate up to 10 descriptive tags for each image
4. THE Vision_Analyzer SHALL download the image from S3 using the Media_Downloader and encode it as base64 for the API request
5. IF the OpenAI Vision API returns an error for a specific image, THEN THE Vision_Analyzer SHALL skip that image and continue processing remaining images
6. THE AI_Service SHALL store image analysis results in the AIAnalysis_Model `image_analyses` JSON field as a list of objects containing `media_url`, `caption`, and `tags`

### Requirement 5: Video Caption and Summary Generation

**User Story:** As a capsule owner, I want AI-generated summaries of my video messages, so that I get a quick overview of what the video contains.

#### Acceptance Criteria

1. WHEN a capsule with video media files (.mp4, .mov, .avi, .webm) is unlocked, THE AI_Service SHALL first extract audio from the video and transcribe it using the Transcription_Service
2. WHEN a video transcription is available, THE Summary_Generator SHALL generate a summary of the video content based on the transcription
3. THE AI_Service SHALL store video-specific summaries in the AIAnalysis_Model `video_summaries` JSON field as a list of objects containing `media_url`, `transcription`, and `summary`
4. IF audio extraction fails for a video, THEN THE AI_Service SHALL skip that video and log the error without blocking other analyses
5. IF the video has no audible speech, THEN THE Transcription_Service SHALL return an empty string and THE Summary_Generator SHALL note that the video contained no speech

### Requirement 6: Expanded AIAnalysis Database Model

**User Story:** As a developer, I want the AIAnalysis model to store all enrichment data, so that all AI insights are persisted and retrievable.

#### Acceptance Criteria

1. THE AIAnalysis_Model SHALL include the following fields: `summary` (Text, nullable), `sentiment_label` (String, nullable), `sentiment_confidence` (Float, nullable), `tone_description` (Text, nullable), `image_analyses` (JSON, nullable), `video_summaries` (JSON, nullable), `recap_text` (Text, nullable), `processing_status` (String, default "pending"), `error_message` (Text, nullable)
2. THE AIAnalysis_Model SHALL retain the existing `id`, `capsule_id`, `created_at` fields and the relationship to the Capsule model
3. THE AIAnalysis_Model `processing_status` field SHALL accept one of: "pending", "processing", "completed", "failed"
4. WHEN the AI_Service begins analysis, THE AI_Service SHALL create an AIAnalysis record with `processing_status` set to "pending"
5. WHEN the AI_Service completes all analyses, THE AI_Service SHALL update `processing_status` to "completed"
6. IF any analysis step fails critically, THEN THE AI_Service SHALL set `processing_status` to "failed" and store the error in `error_message`

### Requirement 7: Memory Recap Generation

**User Story:** As a capsule owner, I want a beautiful AI-generated recap of my stored memory at unlock time, so that I experience a meaningful moment before seeing the original content.

#### Acceptance Criteria

1. WHEN all individual analyses (summary, sentiment, image captions, video summaries) are complete, THE Recap_Generator SHALL generate a unified memory recap combining all available AI insights
2. THE Recap_Generator SHALL produce a narrative-style recap (150-300 words) that weaves together the text summary, emotional tone, image descriptions, and video summaries into a cohesive reflection
3. THE Recap_Generator SHALL include temporal context referencing how much time has passed since the capsule was created
4. THE Recap_Generator SHALL use the OpenAI Chat Completions API with a prompt that emphasizes warmth, nostalgia, and personal reflection
5. IF no AI insights are available (all analyses failed), THEN THE Recap_Generator SHALL return None
6. THE AI_Service SHALL store the recap in the AIAnalysis_Model `recap_text` field

### Requirement 8: Backend API Response with Full AI Analysis

**User Story:** As a frontend developer, I want the capsule API to return all AI analysis data, so that I can display enriched content to the user.

#### Acceptance Criteria

1. WHEN a capsule is retrieved via the GET `/api/capsules/{id}` endpoint and the capsule is unlocked, THE Capsule API SHALL include the full AIAnalysis data in the `ai_analysis` response field
2. THE `ai_analysis` response object SHALL include: `summary`, `sentiment_label`, `sentiment_confidence`, `tone_description`, `image_analyses`, `video_summaries`, `recap_text`, `processing_status`, and `created_at`
3. WHILE the AIAnalysis `processing_status` is "pending" or "processing", THE Capsule API SHALL return the `ai_analysis` object with `processing_status` indicating the current state so the frontend can show a loading indicator
4. IF no AIAnalysis record exists for the capsule, THEN THE Capsule API SHALL return `ai_analysis` as null

### Requirement 9: Frontend Display of AI Enrichment Results

**User Story:** As a capsule owner, I want to see all AI-generated insights displayed beautifully on the capsule detail page, so that my memory experience is enriched.

#### Acceptance Criteria

1. WHEN a capsule is unlocked and has a `recap_text`, THE Capsule_Detail_Page SHALL display the Memory_Recap_View as the first section before showing original content
2. THE Memory_Recap_View SHALL display the recap text in a visually distinct card with a gradient background and decorative elements
3. WHEN a capsule has `sentiment_label` and `tone_description`, THE Capsule_Detail_Page SHALL display a sentiment badge showing the emotion label and tone description
4. WHEN a capsule has `image_analyses`, THE Capsule_Detail_Page SHALL display AI-generated captions below each corresponding image and show tags as pill-shaped badges
5. WHEN a capsule has `video_summaries`, THE Capsule_Detail_Page SHALL display the AI-generated summary below each corresponding video player
6. WHILE the `processing_status` is "pending" or "processing", THE Capsule_Detail_Page SHALL display an animated loading indicator with the message "AI is analyzing your memories..."
7. IF the `processing_status` is "failed", THEN THE Capsule_Detail_Page SHALL display the original content without AI enrichment and show a subtle notice that AI analysis was unavailable

### Requirement 10: Frontend AIAnalysis Type Expansion

**User Story:** As a frontend developer, I want the TypeScript types to match the expanded API response, so that the frontend can safely consume all AI analysis fields.

#### Acceptance Criteria

1. THE `AIAnalysisResponse` TypeScript interface SHALL include: `summary` (string | null), `sentiment_label` (string | null), `sentiment_confidence` (number | null), `tone_description` (string | null), `image_analyses` (array of objects with `media_url`, `caption`, `tags` fields, or null), `video_summaries` (array of objects with `media_url`, `transcription`, `summary` fields, or null), `recap_text` (string | null), `processing_status` (string), and `created_at` (string)
2. THE `CapsuleResponse` interface SHALL retain the existing `ai_analysis` optional field typed as `AIAnalysisResponse | null`

### Requirement 11: AI Analysis Orchestration and Error Isolation

**User Story:** As a developer, I want each AI analysis step to be isolated so that a failure in one step does not prevent other analyses from completing.

#### Acceptance Criteria

1. THE AI_Service SHALL execute analysis steps in the following order: transcription (audio/video), sentiment detection (text), image analysis, summary generation, recap generation
2. IF any individual analysis step fails, THEN THE AI_Service SHALL log the error, continue with the remaining steps, and include partial results in the AIAnalysis record
3. THE AI_Service SHALL update the AIAnalysis `processing_status` to "completed" when all steps have been attempted, regardless of individual step failures
4. THE AI_Service SHALL only set `processing_status` to "failed" when a critical unrecoverable error occurs (e.g., database connection failure)
5. THE Celery task SHALL trigger the AI_Service analysis asynchronously after capsule unlock, with retry logic (max 3 retries, exponential backoff)
