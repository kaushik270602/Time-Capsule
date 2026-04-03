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


def _add_column_if_not_exists(conn, table: str, column: str, col_type: str) -> None:
    """Add a column to a table if it does not already exist."""
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    if result.fetchone() is None:
        conn.execute(text(f'ALTER TABLE {table} ADD COLUMN "{column}" {col_type}'))
        logger.info(f"Added column {column} to {table}")
    else:
        logger.info(f"Column {column} already exists in {table}, skipping")


def _migrate_ai_analysis_fields(conn) -> None:
    """Add new AI enrichment columns to the ai_analysis table."""
    columns = [
        ("sentiment_label", "VARCHAR(20)"),
        ("sentiment_confidence", "FLOAT"),
        ("tone_description", "TEXT"),
        ("image_analyses", "JSON"),
        ("video_summaries", "JSON"),
        ("recap_text", "TEXT"),
        ("processing_status", "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
        ("error_message", "TEXT"),
    ]
    for col_name, col_type in columns:
        _add_column_if_not_exists(conn, "ai_analysis", col_name, col_type)

    # Add check constraint for processing_status if not present
    result = conn.execute(
        text(
            "SELECT 1 FROM information_schema.check_constraints "
            "WHERE constraint_name = 'check_processing_status'"
        )
    )
    if result.fetchone() is None:
        conn.execute(
            text(
                "ALTER TABLE ai_analysis ADD CONSTRAINT check_processing_status "
                "CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed'))"
            )
        )
        logger.info("Added check_processing_status constraint to ai_analysis")
    else:
        logger.info("check_processing_status constraint already exists, skipping")


def run_migrations() -> bool:
    """Create all tables from SQLAlchemy metadata. Returns True on success."""
    logger.info("Starting database migration...")

    if not check_connection():
        logger.error("Cannot connect to database. Check DATABASE_URL.")
        return False

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("All tables created successfully.")

        # Run column-level migrations for existing tables
        with engine.begin() as conn:
            _migrate_ai_analysis_fields(conn)
        logger.info("Column migrations completed.")

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
