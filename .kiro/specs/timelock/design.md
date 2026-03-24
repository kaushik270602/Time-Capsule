# Design Document: TimeLock - AI Powered Digital Time Capsule

## Overview

TimeLock is a full-stack web application built with a React/Next.js frontend and FastAPI backend. The system implements a time-based content locking mechanism where multimedia capsules remain inaccessible until a predetermined unlock date. A background scheduler (Celery) continuously monitors capsules and automatically unlocks them when their unlock date arrives, triggering AI analysis and notifications. The architecture separates concerns into distinct layers: presentation (Next.js), API (FastAPI), business logic (Python services), data persistence (PostgreSQL), media storage (S3/Cloudinary), task queue (Celery + Redis), and AI services (OpenAI API, Whisper).

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Next.js Frontend (React + TailwindCSS)                   │  │
│  │  - Authentication UI                                       │  │
│  │  - Capsule Creation/Management                            │  │
│  │  - Dashboard & Public Feed                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTPS/REST
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI Backend                                          │  │
│  │  - Authentication endpoints                               │  │
│  │  - Capsule CRUD endpoints                                 │  │
│  │  - Media upload endpoints                                 │  │
│  │  - Public feed endpoints                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Business Logic Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Auth Service │  │Capsule Service│  │ AI Service           │ │
│  │ - JWT tokens │  │ - Locking     │  │ - Summary generation │ │
│  │ - Password   │  │ - Validation  │  │ - Sentiment analysis │ │
│  │   hashing    │  │ - Access ctrl │  │ - Transcription      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │Media Service │  │Notification   │  │ Scheduler Service    │ │
│  │ - Upload     │  │   Service     │  │ - Unlock monitoring  │ │
│  │ - Retrieval  │  │ - Email       │  │ - Celery tasks       │ │
│  │ - URL gen    │  │ - Push/In-app │  │ - Retry logic        │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data & External Services                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ PostgreSQL   │  │ Redis        │  │ S3/Cloudinary        │ │
│  │ - Users      │  │ - Task queue │  │ - Media files        │ │
│  │ - Capsules   │  │ - Cache      │  │ - CDN delivery       │ │
│  │ - AI Analysis│  │ - Sessions   │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ OpenAI API   │  │ Whisper API  │                            │
│  │ - GPT-4      │  │ - Speech-to- │                            │
│  │ - Summaries  │  │   text       │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack Rationale


- **Next.js**: Server-side rendering for SEO, built-in routing, API routes for BFF pattern
- **FastAPI**: High performance, automatic OpenAPI docs, async support, type hints
- **PostgreSQL**: ACID compliance, complex queries, JSON support, reliable for time-critical operations
- **Celery + Redis**: Distributed task queue for scheduled unlocking, retry mechanisms, scalability
- **S3/Cloudinary**: Scalable media storage, CDN integration, cost-effective for large files
- **OpenAI API**: State-of-the-art language models for summaries and sentiment analysis
- **Whisper**: Accurate speech-to-text transcription supporting multiple languages

## Components and Interfaces

### 1. Authentication System

**Components:**
- `AuthService`: Handles user registration, login, password reset
- `JWTManager`: Creates and validates JWT tokens
- `PasswordHasher`: Hashes and verifies passwords using bcrypt

**Interfaces:**

```python
class AuthService:
    def register_user(email: str, password: str) -> User:
        """
        Creates new user account with hashed password.
        Sends verification email.
        Returns User object.
        Raises: EmailAlreadyExistsError, InvalidEmailError
        """
    
    def verify_email(token: str) -> bool:
        """
        Marks user account as verified.
        Returns True if successful.
        Raises: InvalidTokenError, ExpiredTokenError
        """
    
    def login(email: str, password: str) -> tuple[User, str]:
        """
        Validates credentials and returns User and JWT token.
        Raises: InvalidCredentialsError, UnverifiedEmailError
        """
    
    def request_password_reset(email: str) -> None:
        """
        Sends password reset email with token.
        Raises: UserNotFoundError
        """
    
    def reset_password(token: str, new_password: str) -> bool:
        """
        Updates user password with new hash.
        Returns True if successful.
        Raises: InvalidTokenError, ExpiredTokenError
        """

class JWTManager:
    def create_token(user_id: int, expiration_hours: int = 24) -> str:
        """
        Creates JWT token with user_id claim and expiration.
        Returns encoded token string.
        """
    
    def validate_token(token: str) -> int:
        """
        Validates token signature and expiration.
        Returns user_id from claims.
        Raises: InvalidTokenError, ExpiredTokenError
        """
```


### 2. Capsule Management System

**Components:**
- `CapsuleService`: Core business logic for capsule CRUD operations
- `LockingMechanism`: Enforces time-based access control
- `AccessController`: Validates user permissions

**Interfaces:**

```python
class CapsuleService:
    def create_capsule(
        user_id: int,
        title: str,
        text_content: str,
        unlock_date: datetime,
        is_public: bool = False,
        media_urls: list[str] = []
    ) -> Capsule:
        """
        Creates new capsule with status "locked".
        Validates unlock_date is in future.
        Returns Capsule object.
        Raises: InvalidUnlockDateError, ValidationError
        """
    
    def get_capsule(capsule_id: int, requesting_user_id: int) -> Capsule:
        """
        Retrieves capsule if user has access.
        Enforces locking mechanism.
        Returns Capsule object with content if unlocked.
        Raises: AccessDeniedError, CapsuleNotFoundError
        """
    
    def list_user_capsules(
        user_id: int,
        filter_status: str = None,
        search_query: str = None
    ) -> list[Capsule]:
        """
        Returns list of user's capsules with filters applied.
        Locked capsules return metadata only (no content).
        """
    
    def get_public_feed(limit: int = 50, offset: int = 0) -> list[Capsule]:
        """
        Returns recently unlocked public capsules.
        Sorted by unlock_date descending.
        """

class LockingMechanism:
    def is_locked(capsule: Capsule) -> bool:
        """
        Returns True if capsule status is "locked" or unlock_date not reached.
        """
    
    def can_access_content(capsule: Capsule, user_id: int) -> bool:
        """
        Returns True if user can access capsule content.
        Checks: ownership, unlock status, public/private.
        """
    
    def get_content_or_deny(capsule: Capsule, user_id: int) -> dict:
        """
        Returns capsule content if access allowed.
        Returns metadata only if locked.
        Raises: AccessDeniedError if unauthorized.
        """
```


### 3. Scheduler and Unlock System

**Components:**
- `UnlockScheduler`: Celery periodic task that monitors and unlocks capsules
- `UnlockOrchestrator`: Coordinates unlock process including AI analysis and notifications

**Interfaces:**

```python
class UnlockScheduler:
    @celery.task
    def check_and_unlock_capsules() -> None:
        """
        Periodic task (runs every minute).
        Queries capsules where unlock_date <= now AND status = "locked".
        Calls unlock_capsule for each.
        """
    
    def unlock_capsule(capsule_id: int) -> bool:
        """
        Changes capsule status to "unlocked".
        Logs unlock event.
        Triggers AI analysis and notifications.
        Returns True if successful.
        Implements retry logic on failure.
        """

class UnlockOrchestrator:
    def process_unlock(capsule_id: int) -> None:
        """
        Orchestrates complete unlock workflow:
        1. Update capsule status
        2. Log unlock event
        3. Trigger AI analysis (async)
        4. Send notifications (async)
        Uses database transaction for atomicity.
        """
    
    def retry_failed_unlock(capsule_id: int, attempt: int) -> None:
        """
        Retries unlock with exponential backoff.
        Max 3 attempts.
        Logs failures for manual intervention.
        """
```

### 4. Media Storage System

**Components:**
- `MediaService`: Handles upload, storage, and retrieval of media files
- `StorageAdapter`: Abstraction layer for S3/Cloudinary

**Interfaces:**

```python
class MediaService:
    def upload_media(
        file: UploadFile,
        user_id: int,
        media_type: str
    ) -> str:
        """
        Validates file format and size.
        Uploads to storage service.
        Returns secure URL.
        Raises: InvalidFileError, UploadFailedError
        """
    
    def validate_file(file: UploadFile, media_type: str) -> bool:
        """
        Checks file format and size limits.
        Video: max 500MB, formats: MP4, MOV, AVI
        Audio: max 100MB, formats: MP3, WAV, M4A
        Image: max 10MB, formats: JPG, PNG, GIF
        Returns True if valid.
        Raises: InvalidFileError
        """
    
    def generate_secure_url(
        file_key: str,
        capsule_id: int,
        expiration_seconds: int = 3600
    ) -> str:
        """
        Generates time-limited signed URL.
        Includes capsule_id for access control validation.
        """
    
    def delete_media(file_key: str) -> bool:
        """
        Removes media file from storage.
        Returns True if successful.
        """
```


### 5. AI Analysis System

**Components:**
- `AIService`: Orchestrates all AI operations
- `SummaryGenerator`: Creates contextual summaries using GPT-4
- `TranscriptionService`: Converts audio/video to text using Whisper

**Interfaces:**

```python
class AIService:
    def analyze_capsule(capsule_id: int) -> AIAnalysis:
        """
        Performs AI analysis on unlocked capsule.
        Calls summary generator.
        Stores results in AI_Analysis table.
        Returns AIAnalysis object.
        Handles failures gracefully (logs and continues).
        """
    
    def transcribe_media(media_url: str, media_type: str) -> str:
        """
        Downloads media file.
        Calls Whisper API for transcription.
        Returns transcribed text.
        Raises: TranscriptionFailedError
        """

class SummaryGenerator:
    def generate_summary(
        text_content: str,
        transcriptions: list[str],
        created_at: datetime,
        unlocked_at: datetime
    ) -> str:
        """
        Creates contextual summary using GPT-4.
        Includes temporal context (time elapsed).
        Prompt: "Summarize this time capsule message created {time_ago}..."
        Returns summary text (max 200 words).
        """
```


### 6. Notification System

**Components:**
- `NotificationService`: Orchestrates all notification channels
- `EmailNotifier`: Sends email notifications
- `PushNotifier`: Sends push notifications
- `InAppNotifier`: Creates in-app notifications

**Interfaces:**

```python
class NotificationService:
    def notify_unlock(capsule_id: int) -> None:
        """
        Sends notifications through all enabled channels.
        Runs asynchronously (Celery task).
        Logs delivery status.
        Implements retry logic for failures.
        """
    
    def send_email(user_id: int, capsule: Capsule) -> bool:
        """
        Sends email notification with capsule details and link.
        Returns True if sent successfully.
        Retries up to 3 times on failure.
        """
    
    def send_push(user_id: int, capsule: Capsule) -> bool:
        """
        Sends push notification to registered devices.
        Returns True if sent successfully.
        Only if user has push enabled.
        """
    
    def create_in_app_notification(user_id: int, capsule: Capsule) -> None:
        """
        Creates notification record in database.
        Visible in user dashboard.
        Includes capsule link and unlock timestamp.
        """
```

## Data Models

### Database Schema

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- Capsules table
CREATE TABLE capsules (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    text_content TEXT,
    media_urls JSONB DEFAULT '[]',
    transcriptions JSONB DEFAULT '[]',
    unlock_date TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('locked', 'unlocked')),
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT future_unlock_date CHECK (unlock_date > created_at)
);

CREATE INDEX idx_capsules_user_id ON capsules(user_id);
CREATE INDEX idx_capsules_unlock_date ON capsules(unlock_date);
CREATE INDEX idx_capsules_status ON capsules(status);
CREATE INDEX idx_capsules_public_unlocked ON capsules(is_public, status, unlock_date) 
    WHERE is_public = TRUE AND status = 'unlocked';

-- Unlock log table
CREATE TABLE unlock_log (
    id SERIAL PRIMARY KEY,
    capsule_id INTEGER NOT NULL REFERENCES capsules(id) ON DELETE CASCADE,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notification_sent BOOLEAN DEFAULT FALSE,
    email_sent BOOLEAN DEFAULT FALSE,
    push_sent BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_unlock_log_capsule_id ON unlock_log(capsule_id);

-- AI Analysis table
CREATE TABLE ai_analysis (
    id SERIAL PRIMARY KEY,
    capsule_id INTEGER NOT NULL REFERENCES capsules(id) ON DELETE CASCADE,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ai_analysis_capsule_id ON ai_analysis(capsule_id);

-- In-app notifications table
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    capsule_id INTEGER NOT NULL REFERENCES capsules(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notifications_user_id ON notifications(user_id, is_read);
```


### API Data Models

```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class UserResponse(BaseModel):
    id: int
    email: str
    is_verified: bool
    created_at: datetime

class CapsuleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text_content: Optional[str] = None
    unlock_date: datetime
    is_public: bool = False
    
    @validator('unlock_date')
    def validate_future_date(cls, v):
        if v <= datetime.utcnow():
            raise ValueError('unlock_date must be in the future')
        return v

class CapsuleResponse(BaseModel):
    id: int
    user_id: int
    title: str
    text_content: Optional[str]  # None if locked
    media_urls: list[str]
    unlock_date: datetime
    status: str
    is_public: bool
    created_at: datetime
    time_until_unlock: Optional[int]  # seconds, None if unlocked
    ai_analysis: Optional[AIAnalysisResponse]

class AIAnalysisResponse(BaseModel):
    summary: Optional[str]
    created_at: datetime

class NotificationResponse(BaseModel):
    id: int
    capsule_id: int
    message: str
    is_read: bool
    created_at: datetime
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Authentication and User Management Properties

**Property 1: User registration creates valid accounts**
*For any* valid email and password combination, registering a new user should create an account with hashed password and trigger a verification email.
**Validates: Requirements 1.1, 1.2, 1.10**

**Property 2: Duplicate email registration is rejected**
*For any* email address that already exists in the system, attempting to register with that email should be rejected with an error message.
**Validates: Requirements 1.4**

**Property 3: Email verification activates accounts**
*For any* unverified user account, clicking the verification link should mark the account as verified and enable full access.
**Validates: Requirements 1.3**

**Property 4: Valid credentials grant access**
*For any* registered and verified user, providing correct email and password should return a valid JWT token with expiration time.
**Validates: Requirements 1.5, 1.7**

**Property 5: Invalid credentials are rejected**
*For any* login attempt with incorrect email or password, the system should reject the attempt and return an error message without revealing which field was incorrect.
**Validates: Requirements 1.6**

**Property 6: Password reset flow updates credentials**
*For any* registered user, requesting password reset should send a reset link, and using that link to set a new password should update the password hash and allow login with the new password.
**Validates: Requirements 1.8, 1.9**

**Property 7: Sensitive operations require re-authentication**
*For any* attempt to change email or password, the system should require valid current credentials before allowing the change.
**Validates: Requirements 2.4**


### Capsule Creation and Validation Properties

**Property 8: Capsules require title**
*For any* capsule creation attempt without a title, the system should reject the creation and return a validation error.
**Validates: Requirements 3.1**

**Property 9: Media file validation enforces format and size limits**
*For any* media file upload (video, audio, or image), the system should validate format and size against defined limits, rejecting files that exceed limits or have unsupported formats with descriptive error messages.
**Validates: Requirements 3.3, 3.4, 3.5, 3.7, 3.8, 14.7, 14.8, 14.9**

**Property 10: Media files are stored with retrievable URLs**
*For any* valid media file upload, the system should store the file in Media_Storage and save a secure URL in the database that can be used for future retrieval.
**Validates: Requirements 3.6, 14.1, 14.2**

**Property 11: Privacy defaults to private**
*For any* capsule created without an explicit privacy setting, the system should set is_public to false.
**Validates: Requirements 3.10**

**Property 12: Unlock date must be in future**
*For any* capsule creation or update, if the unlock_date is not in the future, the system should reject the operation and return a validation error.
**Validates: Requirements 4.1, 4.2**

**Property 13: Unlock dates are stored in UTC**
*For any* capsule with a valid unlock_date, the system should store the timestamp in UTC format regardless of the timezone provided by the user.
**Validates: Requirements 4.3**

**Property 14: New capsules are locked**
*For any* newly created capsule, the system should set Content_Status to "locked" automatically.
**Validates: Requirements 4.5, 5.1**


### Content Locking and Access Control Properties

**Property 15: Locked capsule content is inaccessible**
*For any* capsule with Content_Status "locked" or where current time is before unlock_date, attempting to access the capsule content should be denied with an error, returning only metadata (title, unlock_date, status).
**Validates: Requirements 5.2, 5.4, 5.6**

**Property 16: Locked capsules are immutable**
*For any* capsule with Content_Status "locked", attempting to modify or delete the capsule content should be rejected with an error.
**Validates: Requirements 5.3**

**Property 17: Locked capsules display countdown**
*For any* locked capsule in a user's capsule list, the response should include a locked indicator and time remaining until unlock_date.
**Validates: Requirements 5.5, 8.3**

**Property 18: Private capsules are owner-only**
*For any* private capsule (is_public = false), only the capsule owner should be able to access the capsule, regardless of lock status.
**Validates: Requirements 9.9, 17.8**

**Property 19: Public capsules are hidden when locked**
*For any* public capsule (is_public = true) with Content_Status "locked", the capsule should not appear in the public feed or be accessible to any user including the owner's content access.
**Validates: Requirements 9.2**

**Property 20: Unlocked public capsules are visible to all**
*For any* public capsule with Content_Status "unlocked", the capsule should appear in the public feed and be accessible to all users including unauthenticated users.
**Validates: Requirements 9.3, 9.6, 9.7**

**Property 21: Locked capsule privacy is immutable**
*For any* locked capsule, attempting to change the is_public setting should be rejected with an error.
**Validates: Requirements 9.8**


### Automatic Unlocking Properties

**Property 22: Capsules unlock when time arrives**
*For any* capsule where current time >= unlock_date and Content_Status is "locked", the scheduler should change Content_Status to "unlocked" and log the event in Unlock_Log.
**Validates: Requirements 6.1, 6.3**

**Property 23: Unlock triggers notifications and AI analysis**
*For any* capsule that transitions from "locked" to "unlocked", the system should trigger both the notification process and AI analysis generation.
**Validates: Requirements 6.4, 6.5**

**Property 24: Failed unlocks are retried**
*For any* unlock operation that fails, the system should retry the operation with exponential backoff up to a maximum number of attempts.
**Validates: Requirements 6.6**

**Property 25: Unlocks are processed in order**
*For any* set of capsules ready to unlock, the scheduler should process them in order of unlock_date (earliest first).
**Validates: Requirements 6.7**

### Notification Properties

**Property 26: Unlock notifications are sent through all channels**
*For any* capsule unlock event, the system should send an email notification, create an in-app notification, and (if enabled) send a push notification to the capsule owner.
**Validates: Requirements 7.1, 7.2, 7.3**

**Property 27: Notifications contain required information**
*For any* unlock notification sent through any channel, the notification should include the capsule title, unlock date, and a direct link to view the capsule.
**Validates: Requirements 7.6, 7.7**

**Property 28: Notification delivery is logged**
*For any* notification sent, the system should record the delivery status (email_sent, push_sent, notification_sent) in the Unlock_Log.
**Validates: Requirements 7.4**

**Property 29: Failed email notifications are retried**
*For any* email notification that fails to send, the system should retry delivery up to three times before marking as failed.
**Validates: Requirements 7.5**


### Dashboard and Search Properties

**Property 30: Dashboard displays all user capsules**
*For any* user accessing their dashboard, the system should return all capsules owned by that user, separated into locked and unlocked sections.
**Validates: Requirements 8.1, 8.2**

**Property 31: Dashboard statistics are accurate**
*For any* user's dashboard, the displayed statistics (total capsules, locked count, unlocked count) should match the actual counts in the database.
**Validates: Requirements 8.8**

**Property 32: Capsule filters work correctly**
*For any* filter applied to the capsule list (by status, date range, etc.), only capsules matching the filter criteria should be returned.
**Validates: Requirements 8.5**

**Property 33: Capsule search includes all text content**
*For any* search query, the system should return capsules where the query matches the title, text content, or transcription text.
**Validates: Requirements 8.6, 13.4**

**Property 34: Capsules are sorted by unlock date**
*For any* capsule list request without explicit sorting, capsules should be sorted by unlock_date with nearest dates first.
**Validates: Requirements 8.7**

**Property 35: Public feed shows recent unlocked public capsules**
*For any* public feed request, the system should return only capsules where is_public = true AND status = "unlocked", sorted by unlock_date descending, with required fields (title, creator, unlock_date, preview).
**Validates: Requirements 9.4, 9.5**


### AI Analysis Properties

**Property 36: AI summary is generated on unlock**
*For any* capsule that unlocks, the system should generate an AI summary and store it in the AI_Analysis table linked to the capsule.
**Validates: Requirements 10.1, 10.4**

**Property 37: AI summaries include temporal context**
*For any* AI summary generated, the summary should reference the time elapsed between capsule creation and unlock.
**Validates: Requirements 10.2**

**Property 38: AI summaries include transcriptions**
*For any* capsule with transcribed audio or video content, the transcription text should be included in the AI summary generation.
**Validates: Requirements 10.3**

**Property 39: AI summary failures are graceful**
*For any* AI summary generation that fails, the system should log the error and still allow capsule access without the summary.
**Validates: Requirements 10.5**

**Property 40: AI summaries are displayed with capsules**
*For any* unlocked capsule viewed by a user, if an AI summary exists, it should be included in the response.
**Validates: Requirements 10.7**


### Transcription Properties

**Property 41: Audio and video files are transcribed**
*For any* audio file (MP3, WAV, M4A) or video file (MP4, MOV, AVI) uploaded to a capsule, the system should transcribe the audio content to text using Whisper AI and store the transcription linked to the capsule.
**Validates: Requirements 13.1, 13.2, 13.3, 13.8, 13.9**

**Property 42: Transcription failures are graceful**
*For any* transcription operation that fails, the system should log the error and store the media file without transcription, allowing the capsule to be created successfully.
**Validates: Requirements 13.5**

**Property 43: Transcriptions are displayed with media**
*For any* unlocked capsule with transcribed media, the transcription text should be included in the response alongside the media file URL.
**Validates: Requirements 13.7**

### Media Storage Properties

**Property 44: Media URLs enforce access control**
*For any* media file associated with a locked capsule, attempting to access the media URL should be denied unless the capsule is unlocked and the user has access rights.
**Validates: Requirements 14.4**

**Property 45: Media upload is verified before confirmation**
*For any* media upload operation, the system should verify successful storage in Media_Storage before returning success to the user.
**Validates: Requirements 14.5**

**Property 46: Failed media uploads are retried**
*For any* media upload that fails, the system should retry the upload up to three times before returning an error to the user.
**Validates: Requirements 14.6**


### Error Handling and Validation Properties

**Property 47: Invalid inputs return descriptive errors**
*For any* user input that fails validation, the system should return a descriptive error message indicating which field failed and why.
**Validates: Requirements 15.1**

**Property 48: Required fields are validated**
*For any* form submission, the system should validate that all required fields are present and non-empty before processing.
**Validates: Requirements 15.2**

**Property 49: External service failures trigger retries**
*For any* external service call (AI API, email service, media storage) that fails, the system should implement retry logic with exponential backoff.
**Validates: Requirements 15.4**

**Property 50: Errors are logged for debugging**
*For any* error that occurs (validation, database, external service), the system should log detailed error information including timestamp, user context, and stack trace.
**Validates: Requirements 15.5, 17.9**

**Property 51: Email format is validated**
*For any* email address provided during registration or profile update, the system should validate the format matches standard email patterns before accepting.
**Validates: Requirements 15.6**

**Property 52: Password strength is enforced**
*For any* password provided during registration or password change, the system should validate it meets minimum requirements (8+ characters, mixed case, numbers) before accepting.
**Validates: Requirements 15.7**

**Property 53: Rate limiting prevents abuse**
*For any* authentication endpoint (login, registration, password reset), the system should implement rate limiting to prevent brute force attacks, returning appropriate error codes when limits are exceeded.
**Validates: Requirements 15.8, 17.6**


### Security Properties

**Property 54: Passwords are always hashed**
*For any* password stored in the database, the value should be a bcrypt or Argon2 hash, never plaintext.
**Validates: Requirements 17.1**

**Property 55: CSRF protection is enforced**
*For any* state-changing API operation (POST, PUT, DELETE), the system should require a valid CSRF token.
**Validates: Requirements 17.3**

**Property 56: User inputs are sanitized**
*For any* user input that will be stored or displayed, the system should sanitize the input to prevent injection attacks (SQL, XSS, command injection).
**Validates: Requirements 17.4**

**Property 57: Expired sessions require re-authentication**
*For any* request with an expired JWT token, the system should reject the request and require the user to log in again.
**Validates: Requirements 17.5**

**Property 58: Session tokens are secure**
*For any* session token created, it should be stored with httpOnly and secure flags to prevent client-side access and ensure HTTPS-only transmission.
**Validates: Requirements 17.7**

### Database Integrity Properties

**Property 59: Timestamps are set automatically**
*For any* capsule created, the created_at timestamp should be set automatically to the current time, and for any capsule unlocked, the unlocked_at timestamp should be recorded in Unlock_Log.
**Validates: Requirements 18.4, 18.5**

**Property 60: Database transactions maintain consistency**
*For any* operation that modifies multiple tables (e.g., unlocking a capsule, creating AI analysis, logging unlock), the system should use database transactions to ensure all changes succeed or all are rolled back.
**Validates: Requirements 18.9**

**Property 61: Caching improves performance**
*For any* frequently accessed data (public feed, user dashboard), the system should use caching to reduce database load, with cache invalidation when underlying data changes.
**Validates: Requirements 16.6**


## Error Handling

### Error Categories and Responses

**Validation Errors (400 Bad Request)**
- Invalid email format
- Weak password
- Missing required fields
- Past unlock date
- Unsupported media format
- File size exceeded

Response format:
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "details": [
    {
      "field": "unlock_date",
      "message": "Unlock date must be in the future"
    }
  ]
}
```

**Authentication Errors (401 Unauthorized)**
- Invalid credentials
- Expired token
- Unverified email
- Missing authentication

Response format:
```json
{
  "error": "authentication_error",
  "message": "Invalid credentials"
}
```

**Authorization Errors (403 Forbidden)**
- Accessing locked capsule content
- Accessing another user's private capsule
- Modifying locked capsule
- Insufficient permissions

Response format:
```json
{
  "error": "authorization_error",
  "message": "Cannot access locked capsule content before unlock date"
}
```

**Not Found Errors (404 Not Found)**
- Capsule not found
- User not found
- Resource not found

Response format:
```json
{
  "error": "not_found",
  "message": "Capsule not found"
}
```

**Rate Limiting Errors (429 Too Many Requests)**
- Too many login attempts
- Too many API requests
- Too many upload attempts

Response format:
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 60
}
```

**Server Errors (500 Internal Server Error)**
- Database connection failure
- External service failure (after retries)
- Unexpected exceptions

Response format:
```json
{
  "error": "internal_error",
  "message": "An unexpected error occurred. Please try again later.",
  "request_id": "uuid-for-tracking"
}
```

### Retry Strategies

**External Service Calls**
- Initial retry: 1 second delay
- Second retry: 2 seconds delay
- Third retry: 4 seconds delay
- Max retries: 3
- Services: AI API, Whisper API, Email service, Media storage

**Database Operations**
- Transient errors: Retry immediately
- Connection errors: Retry with exponential backoff
- Max retries: 3
- Timeout: 30 seconds

**Unlock Operations**
- Failed unlock: Retry after 1 minute
- Max retries: 5
- Alert admin after max retries exceeded

### Graceful Degradation

**AI Analysis Failures**
- If summary generation fails: Capsule still unlocks, no summary displayed
- If sentiment analysis fails: Capsule still unlocks, no sentiment displayed
- If reflection generation fails: Capsule still unlocks, no reflection displayed
- All failures logged for manual review

**Transcription Failures**
- If transcription fails: Media file still stored and accessible
- Transcription marked as failed in database
- Can be retried manually by admin

**Notification Failures**
- If email fails after retries: In-app notification still created
- If push notification fails: Email and in-app still sent
- Failure logged for monitoring


## Testing Strategy

### Dual Testing Approach

TimeLock requires both unit tests and property-based tests for comprehensive coverage. Unit tests validate specific examples and edge cases, while property-based tests verify universal properties across all inputs. Together, they ensure both concrete correctness and general system behavior.

### Property-Based Testing

**Framework**: Use `hypothesis` for Python backend testing

**Configuration**:
- Minimum 100 iterations per property test
- Each test tagged with: `# Feature: timelock, Property {N}: {property_text}`
- Seed randomization for reproducibility
- Shrinking enabled for minimal failing examples

**Property Test Coverage**:

Each correctness property (Properties 1-62) should be implemented as a property-based test. Key areas:

1. **Authentication Properties (1-7)**
   - Generate random valid/invalid emails and passwords
   - Test registration, login, password reset flows
   - Verify token generation and validation

2. **Capsule Creation Properties (8-14)**
   - Generate random capsule data with various media types
   - Test validation rules across all input combinations
   - Verify locking mechanism initialization

3. **Access Control Properties (15-21)**
   - Generate capsules with various lock states and privacy settings
   - Test access from different user contexts
   - Verify content visibility rules

4. **Unlocking Properties (22-25)**
   - Generate capsules with various unlock dates
   - Test scheduler behavior with time manipulation
   - Verify unlock triggers and ordering

5. **Notification Properties (26-29)**
   - Generate unlock events
   - Test notification delivery across channels
   - Verify retry logic with simulated failures

6. **Dashboard and Search Properties (30-35)**
   - Generate users with various capsule collections
   - Test filtering, sorting, and search across all combinations
   - Verify statistics calculations

7. **AI Analysis Properties (36-40)**
   - Generate capsules with various content types
   - Mock AI services to test integration
   - Verify graceful degradation on failures

8. **Transcription Properties (41-43)**
   - Generate media files in supported formats
   - Mock Whisper API to test integration
   - Verify transcription storage and retrieval

9. **Media Storage Properties (44-46)**
   - Generate various media files
   - Mock storage service to test upload/retrieval
   - Verify access control and retry logic

10. **Error Handling Properties (47-53)**
    - Generate invalid inputs of all types
    - Test validation and error responses
    - Verify rate limiting behavior

11. **Security Properties (54-58)**
    - Test password hashing across all passwords
    - Verify CSRF protection on all endpoints
    - Test input sanitization with malicious inputs

12. **Database Properties (59-61)**
    - Test timestamp generation
    - Verify transaction rollback on failures
    - Test cache invalidation

### Unit Testing

**Framework**: Use `pytest` for Python backend, `Jest` for TypeScript frontend

**Unit Test Focus**:

1. **Specific Examples**
   - User registration with specific email formats
   - Capsule creation with specific unlock dates
   - Public feed with specific capsule sets

2. **Edge Cases**
   - Empty text content
   - Maximum file sizes (500MB video, 100MB audio, 10MB images)
   - Unlock date exactly 50 years in future
   - Maximum 20 images per capsule
   - Capsule unlocking at exact unlock_date timestamp

3. **Error Conditions**
   - Database connection failures
   - AI API rate limiting
   - Media storage quota exceeded
   - Email service unavailable

4. **Integration Points**
   - FastAPI endpoint integration
   - Database query execution
   - Celery task execution
   - External service mocking

5. **Database Schema Validation**
   - Foreign key constraints exist (Requirements 18.1-18.3)
   - NOT NULL constraints exist (Requirement 18.6)
   - CHECK constraints exist (Requirements 18.7-18.8)
   - Indexes exist on frequently queried fields (Requirement 16.5)

### Test Organization

```
tests/
├── unit/
│   ├── test_auth_service.py
│   ├── test_capsule_service.py
│   ├── test_locking_mechanism.py
│   ├── test_unlock_scheduler.py
│   ├── test_ai_service.py
│   ├── test_media_service.py
│   ├── test_notification_service.py
│   └── test_api_endpoints.py
├── property/
│   ├── test_auth_properties.py
│   ├── test_capsule_properties.py
│   ├── test_access_control_properties.py
│   ├── test_unlock_properties.py
│   ├── test_notification_properties.py
│   ├── test_dashboard_properties.py
│   ├── test_ai_properties.py
│   ├── test_transcription_properties.py
│   ├── test_media_properties.py
│   ├── test_error_handling_properties.py
│   ├── test_security_properties.py
│   └── test_database_properties.py
├── integration/
│   ├── test_unlock_workflow.py
│   ├── test_capsule_lifecycle.py
│   └── test_public_feed.py
└── fixtures/
    ├── users.py
    ├── capsules.py
    └── media_files.py
```

### Mocking Strategy

**External Services to Mock**:
- OpenAI API (GPT-4 for summaries, sentiment, reflection)
- Whisper API (speech-to-text)
- Email service (SMTP)
- Push notification service
- S3/Cloudinary (media storage)

**Database**:
- Use in-memory PostgreSQL for tests
- Reset database between test runs
- Use transactions for test isolation

**Time Manipulation**:
- Use `freezegun` to control time in tests
- Test unlock scheduler with various time scenarios

### Continuous Integration

**Pre-commit Checks**:
- Run all unit tests
- Run linting (black, flake8, mypy)
- Run type checking

**CI Pipeline**:
- Run all unit tests
- Run all property-based tests
- Run integration tests
- Generate coverage report (target: 85%+)
- Run security scanning (bandit)

### Performance Testing

**Load Testing**:
- Simulate 10,000 concurrent users
- Test dashboard load times (<2 seconds)
- Test capsule creation times (<3 seconds)
- Test scheduler with 100 concurrent unlocks

**Stress Testing**:
- Test with 1 million capsules in database
- Test public feed with 100,000 public capsules
- Test media storage with large files (500MB videos)

