# TimeLock — AI Powered Digital Time Capsule

Create multimedia time capsules, lock them until a future date, and let AI enrich your memories when they unlock.

## Features

- **Time-Locked Capsules** — Text, video, audio, and image content sealed until your chosen unlock date
- **AI Memory Enrichment** — On unlock, AI analyzes your capsule:
  - Text summarization and sentiment/tone detection
  - Audio/video transcription via Whisper
  - Image captioning and tagging via GPT-4o Vision
  - Video summaries from extracted audio
  - Unified "Memory Recap" narrative combining all insights
- **Timezone-Aware Scheduling** — IANA timezone support with DST handling
- **Automatic Unlock** — Celery beat checks every minute and unlocks capsules on schedule
- **Notifications** — In-app notifications when capsules unlock
- **Public Feed** — Share capsules publicly after unlock
- **Mobile Responsive** — Hamburger menu, touch-friendly UI
- **Dark Sidebar UI** — Warm amber/stone color scheme

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React 18, TailwindCSS, TypeScript |
| Backend | FastAPI, Python 3.11, SQLAlchemy, Pydantic v2 |
| Database | PostgreSQL 15 |
| Cache/Queue | Redis 7, Celery |
| AI | OpenAI GPT-4/4o, Whisper |
| Storage | AWS S3 (with local filesystem fallback) |
| Containers | Docker, Docker Compose |

## Quick Start

```bash
# Clone and configure
git clone https://github.com/kaushik270602/Time-Capsule.git
cd Time-Capsule
cp .env.example .env
# Edit .env with your credentials (see Environment below)

# Start everything
docker-compose up -d --build

# Run database migrations
docker exec timelock-backend python -m app.migrate
```

Frontend: http://localhost:3001
Backend API: http://localhost:8000
API Docs: http://localhost:8000/docs

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_USER` | Yes | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `POSTGRES_DB` | Yes | Database name |
| `JWT_SECRET_KEY` | Yes | Secret for JWT signing (`openssl rand -hex 32`) |
| `OPENAI_API_KEY` | No | OpenAI key for AI features (summarization, transcription, vision) |
| `AWS_ACCESS_KEY_ID` | No | AWS credentials for S3 media storage |
| `AWS_SECRET_ACCESS_KEY` | No | AWS credentials for S3 media storage |
| `S3_BUCKET_NAME` | No | S3 bucket for media uploads |
| `SMTP_HOST` | No | SMTP server for email notifications |

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│   Next.js    │────▶│   FastAPI    │────▶│ PostgreSQL │
│  Frontend    │     │   Backend    │     └────────────┘
└─────────────┘     └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌────────────┐
                    │    Celery    │────▶│   Redis    │
                    │  Worker/Beat │     └────────────┘
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌────────────┐
                    │  AI Services │────▶│  OpenAI    │
                    │  (on unlock) │     │  API       │
                    └──────────────┘     └────────────┘
```

## AI Pipeline (on capsule unlock)

1. **Transcription** — Audio/video downloaded from S3, transcribed via Whisper
2. **Sentiment Detection** — Text analyzed for emotional tone (joyful, nostalgic, hopeful, etc.)
3. **Image Analysis** — Photos captioned and tagged via GPT-4o Vision
4. **Summary** — GPT-4 generates a contextual summary with temporal reflection
5. **Memory Recap** — All insights woven into a 150-300 word narrative

Each step is error-isolated — failures in one step don't block others.

## File Size Limits

| Media Type | Max Size | Reason |
|-----------|----------|--------|
| Video | 25 MB | OpenAI Whisper API limit |
| Audio | 25 MB | OpenAI Whisper API limit |
| Images | 10 MB | — |

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models (Capsule, AIAnalysis, User, etc.)
│   │   ├── services/        # Business logic (AIService, SentimentDetector, VisionAnalyzer, etc.)
│   │   ├── routers/         # FastAPI endpoints
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── tasks/           # Celery async tasks (unlock scheduler, AI analysis)
│   │   └── middleware/      # Rate limiting, CSRF, security headers
│   └── tests/               # Property-based tests (Hypothesis) and integration tests
├── frontend/
│   ├── app/                 # Next.js pages (dashboard, capsule detail, auth)
│   ├── components/          # React components (Sidebar, CapsuleCard, MemoryRecapView, etc.)
│   └── lib/                 # API client, timezone utilities
├── docker-compose.yml       # Full stack orchestration
└── .env.example             # Environment template
```

## Development

```bash
# Backend tests
docker exec timelock-backend python -m pytest tests/ -x -q

# Frontend tests
cd frontend && npx jest --passWithNoTests

# Rebuild after code changes
docker-compose up -d --build backend frontend celery-worker
```

## License

MIT
