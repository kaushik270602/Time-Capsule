# TimeLock — Deployment Guide

## Prerequisites

- Docker and Docker Compose v2+
- `curl` (for health checks in deploy script)
- A PostgreSQL-compatible database (provided via Docker)
- (Optional) AWS account with S3 bucket for media storage
- (Optional) OpenAI API key for AI analysis and transcription
- (Optional) SMTP credentials for email notifications

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> && cd timelock

# 2. Create your environment file
cp .env.example .env
# Edit .env with your production values (see Environment Setup below)

# 3. Deploy
chmod +x scripts/deploy.sh scripts/migrate.sh
./scripts/deploy.sh
```

The deploy script will validate your environment, start all containers, run database migrations, and perform health checks.

## Environment Setup

Copy `.env.example` to `.env` and configure the following:

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_USER` | Yes | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `POSTGRES_DB` | Yes | PostgreSQL database name |
| `JWT_SECRET_KEY` | Yes | Secret key for JWT signing — use a strong random value |
| `OPENAI_API_KEY` | No | OpenAI API key for AI summaries, transcription, sentiment detection, image analysis, and memory recaps |
| `AWS_ACCESS_KEY_ID` | No | AWS credentials for S3 media storage |
| `AWS_SECRET_ACCESS_KEY` | No | AWS credentials for S3 media storage |
| `S3_BUCKET_NAME` | No | S3 bucket name for media uploads |
| `SMTP_HOST` | No | SMTP server for email notifications |
| `SMTP_USER` | No | SMTP username |
| `SMTP_PASSWORD` | No | SMTP password |

Generate a secure JWT secret:

```bash
openssl rand -hex 32
```

## Deployment Steps

### Full Deployment

```bash
./scripts/deploy.sh
```

This runs four steps:
1. Validates required environment variables
2. Builds and starts all Docker containers (PostgreSQL, Redis, backend, frontend, Celery worker, Celery beat)
3. Waits for PostgreSQL readiness and runs database migrations
4. Performs health checks on backend and frontend

### Force Rebuild

```bash
./scripts/deploy.sh --build
```

### Stop All Services

```bash
./scripts/deploy.sh --down
```

### Run Migrations Only

```bash
# Inside Docker (recommended)
./scripts/migrate.sh --docker

# Locally (requires Python env with dependencies)
./scripts/migrate.sh
```

## Services

After deployment, the following services are running:

| Service | Default Port | Description |
|---|---|---|
| Frontend | 3000 | Next.js web application |
| Backend | 8000 | FastAPI REST API |
| API Docs | 8000/docs | Swagger UI |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache and task queue |
| Celery Worker | — | Background task processor |
| Celery Beat | — | Periodic task scheduler (capsule unlock checks) |

## AI Analysis

When a capsule unlocks, the system automatically triggers AI analysis via Celery:

1. Audio/video transcription (Whisper API, 25MB file limit)
2. Sentiment/tone detection on text content
3. Image captioning and tagging (GPT-4o Vision)
4. Text summarization with temporal context
5. Unified memory recap generation

Each step is error-isolated. If the `OPENAI_API_KEY` is not set, AI analysis is skipped gracefully.

To manually trigger AI analysis on an already-unlocked capsule:

```bash
curl -X POST http://localhost:8000/api/capsules/{id}/analyze \
  -H "Cookie: <auth-cookie>"
```

Or use the "Analyze with AI" button on the capsule detail page.

## Troubleshooting

### Containers won't start

```bash
# Check container status
docker compose ps

# View logs for a specific service
docker compose logs backend
docker compose logs postgres
```

### Database connection errors

```bash
# Verify PostgreSQL is running and healthy
docker compose exec postgres pg_isready -U timelock

# Check database exists
docker compose exec postgres psql -U timelock -d timelock -c '\dt'
```

### Migration failures

```bash
# Run migration manually with verbose output
docker compose exec backend python -m app.migrate

# Connect to database directly
docker compose exec postgres psql -U timelock -d timelock
```

### Backend not responding

```bash
# Check backend logs
docker compose logs --tail=50 backend

# Restart backend only
docker compose restart backend
```

### Celery tasks not running

```bash
# Check worker logs
docker compose logs celery-worker

# Check beat scheduler logs
docker compose logs celery-beat

# Verify Redis connectivity
docker compose exec redis redis-cli ping
```

### Reset everything

```bash
docker compose down -v   # -v removes volumes (deletes all data)
./scripts/deploy.sh --build
```
