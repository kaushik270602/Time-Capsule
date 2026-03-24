"""
Shared test fixtures for endpoint and integration tests.

All test files that use app.main / app.database should use these fixtures
instead of creating their own engines. This avoids cross-test contamination
when pytest collects multiple files in the same process.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models.base import Base
from app.database import get_db
from app.main import app
from app.middleware.rate_limiter import reset_backend

# Single shared in-memory database for all endpoint tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_shared.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_shared_db():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    reset_backend()
    yield
    app.dependency_overrides[get_db] = override_get_db  # restore in case test changed it
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
