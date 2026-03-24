"""
Database migration script for TimeLock.

Creates all tables defined in SQLAlchemy models using Base.metadata.create_all().
Can be run standalone or imported by other scripts.

Usage:
    python -m app.migrate
"""

import sys
import logging
from sqlalchemy import text

from app.database import engine
from app.models import Base, User, Capsule, UnlockLog, AIAnalysis, Notification  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def check_connection() -> bool:
    """Verify database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def run_migrations() -> bool:
    """Create all tables from SQLAlchemy metadata. Returns True on success."""
    logger.info("Starting database migration...")

    if not check_connection():
        logger.error("Cannot connect to database. Check DATABASE_URL.")
        return False

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("All tables created successfully.")

        # Log created tables
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            tables = [row[0] for row in result]
            logger.info(f"Tables in database: {', '.join(sorted(tables))}")

        return True
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
