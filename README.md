# TimeLock - AI Powered Digital Time Capsule

A production-ready application for creating digital time capsules with AI-powered insights.

## Features

- Create multimedia time capsules (text, video, audio, images)
- Time-based content locking mechanism
- Automatic unlocking with notifications
- AI-powered summaries and speech-to-text
- Public and private capsules
- User dashboard and public feed

## Tech Stack

**Frontend:**
- Next.js 14
- React 18
- TailwindCSS
- TypeScript

**Backend:**
- FastAPI
- PostgreSQL
- Redis
- Celery
- OpenAI API
- Whisper AI

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker and Docker Compose
- PostgreSQL 15+
- Redis 7+

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Start PostgreSQL and Redis with Docker:
```bash
docker-compose up -d
```

3. Create virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

4. Copy environment file and configure:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run database migrations:
```bash
alembic upgrade head
```

6. Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```

API will be available at http://localhost:8000

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm run dev
```

Frontend will be available at http://localhost:3000

## Project Structure

```
timelock/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/
│   │   ├── services/
│   │   ├── api/
│   │   └── utils/
│   ├── requirements.txt
│   └── docker-compose.yml
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── package.json
└── README.md
```

## License

MIT
