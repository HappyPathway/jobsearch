"""Test configuration and fixtures."""
import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from jobsearch.app.main import app
from jobsearch.app.dependencies import get_db
from jobsearch.core.database import Base

# Create test database
@pytest.fixture(scope="session")
def temp_db():
    """Create temporary test database."""
    db_fd, db_path = tempfile.mkstemp()
    db_url = f"sqlite:///{db_path}"
    
    # Create test engine
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session factory
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    
    yield TestingSessionLocal
    
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture
def test_db(temp_db):
    """Get database session for each test."""
    db = temp_db()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(test_db):
    """Create test client with database dependency override."""
    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

@pytest.fixture
def mock_gcs(monkeypatch):
    """Mock GCS storage for testing."""
    class MockGCSManager:
        def __init__(self):
            self.files = {}
            
        def upload_file(self, local_path, gcs_path):
            with open(local_path, 'rb') as f:
                self.files[gcs_path] = f.read()
            
        def download_file(self, gcs_path, local_path):
            if gcs_path in self.files:
                with open(local_path, 'wb') as f:
                    f.write(self.files[gcs_path])
                    
        def sync_db(self):
            pass
            
        def get_download_url(self, gcs_path):
            return f"https://storage.googleapis.com/mock-bucket/{gcs_path}"
    
    monkeypatch.setattr("app.dependencies.storage", MockGCSManager())
    return MockGCSManager()

@pytest.fixture
def test_data_path():
    """Get path to test data directory."""
    return Path(__file__).parent / "data"

@pytest.fixture
def mock_gemini(monkeypatch):
    """Mock Gemini API for testing."""
    class MockGemini:
        def generate_content(self, *args, **kwargs):
            return "Mock generated content"
    
    monkeypatch.setattr("google.generativeai.GenerativeModel", MockGemini)