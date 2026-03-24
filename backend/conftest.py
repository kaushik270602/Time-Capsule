# Root conftest.py — runs before any test module is collected.
# Override DATABASE_URL so that app.database never tries to connect to PostgreSQL
# (psycopg2 may not be installed in the test environment).
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_default.db")
