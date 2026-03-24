#!/usr/bin/env bash
#
# TimeLock - Production Deployment Script
#
# Validates environment, runs migrations, builds containers, and checks health.
#
# Usage:
#   ./scripts/deploy.sh          # Full deploy
#   ./scripts/deploy.sh --build  # Force rebuild images
#   ./scripts/deploy.sh --down   # Stop all services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[deploy]${NC} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${NC} $*"; }
error() { echo -e "${RED}[deploy]${NC} $*" >&2; }

# ── Handle --down flag ──────────────────────────────────────────
if [ "${1:-}" = "--down" ]; then
    log "Stopping all services..."
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" down
    log "All services stopped."
    exit 0
fi

FORCE_BUILD=""
if [ "${1:-}" = "--build" ]; then
    FORCE_BUILD="--build"
fi

# ── Step 1: Validate environment ────────────────────────────────
log "Step 1/4: Validating environment..."

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        warn ".env not found. Copying from .env.example — review and update values."
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    else
        error ".env file not found. Create one from .env.example first."
        exit 1
    fi
fi

set -a
source "$PROJECT_ROOT/.env"
set +a

REQUIRED_VARS=(
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "POSTGRES_DB"
    "JWT_SECRET_KEY"
)

MISSING=0
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        error "Missing required env var: $var"
        MISSING=1
    fi
done

# Warn about production defaults
if [ "${JWT_SECRET_KEY:-}" = "your-secret-key-change-in-production" ]; then
    warn "JWT_SECRET_KEY is set to the default value. Change it for production!"
fi

if [ "$MISSING" -eq 1 ]; then
    error "Fix missing environment variables and retry."
    exit 1
fi

log "Environment validated."

# ── Step 2: Build and start containers ──────────────────────────
log "Step 2/4: Building and starting Docker containers..."

docker compose -f "$PROJECT_ROOT/docker-compose.yml" up -d $FORCE_BUILD

log "Containers started."

# ── Step 3: Wait for services and run migrations ────────────────
log "Step 3/4: Waiting for database and running migrations..."

# Wait for postgres to be healthy (up to 30s)
RETRIES=30
until docker compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T postgres pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" > /dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    if [ "$RETRIES" -le 0 ]; then
        error "PostgreSQL did not become ready in time."
        exit 1
    fi
    sleep 1
done

log "PostgreSQL is ready. Running migrations..."

docker compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T backend python -m app.migrate

log "Migrations complete."

# ── Step 4: Health checks ───────────────────────────────────────
log "Step 4/4: Running health checks..."

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

check_health() {
    local name="$1"
    local url="$2"
    local retries=10

    while [ "$retries" -gt 0 ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            log "$name is healthy."
            return 0
        fi
        retries=$((retries - 1))
        sleep 2
    done
    warn "$name health check failed at $url (service may still be starting)."
    return 1
}

HEALTH_OK=true
check_health "Backend"  "http://localhost:${BACKEND_PORT}/docs" || HEALTH_OK=false
check_health "Frontend" "http://localhost:${FRONTEND_PORT}"      || HEALTH_OK=false

echo ""
log "════════════════════════════════════════"
if [ "$HEALTH_OK" = true ]; then
    log "  Deployment complete!"
else
    warn "  Deployment finished with health check warnings."
fi
log "  Backend:  http://localhost:${BACKEND_PORT}"
log "  Frontend: http://localhost:${FRONTEND_PORT}"
log "  API Docs: http://localhost:${BACKEND_PORT}/docs"
log "════════════════════════════════════════"
