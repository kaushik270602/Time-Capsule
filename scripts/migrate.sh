#!/usr/bin/env bash
#
# TimeLock - Database Migration Script
#
# Creates all tables using SQLAlchemy metadata.
# Can be run standalone or called from deploy.sh.
#
# Usage:
#   ./scripts/migrate.sh              # Run against local/env DATABASE_URL
#   ./scripts/migrate.sh --docker     # Run inside the backend Docker container

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[migrate]${NC} $*"; }
warn()  { echo -e "${YELLOW}[migrate]${NC} $*"; }
error() { echo -e "${RED}[migrate]${NC} $*" >&2; }

# Load .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

USE_DOCKER=false
if [ "${1:-}" = "--docker" ]; then
    USE_DOCKER=true
fi

if [ "$USE_DOCKER" = true ]; then
    log "Running migration inside Docker container..."
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T backend python -m app.migrate
else
    log "Running migration locally..."
    cd "$PROJECT_ROOT/backend"
    python -m app.migrate
fi

if [ $? -eq 0 ]; then
    log "Migration completed successfully."
else
    error "Migration failed."
    exit 1
fi
