"""Tests for document generation and management endpoints."""
import json
from pathlib import Path
import pytest
from datetime import datetime
import tempfile

from jobsearch.core.models import Document

def load_test_data(test_data_path):
    """Load test document data from JSON file."""
    with open(test_data_path / "documents.json") as f:
        return json.load(f)

@pytest.fixture
def test_documents(test_data_path, test_db):
    """Insert test documents into database."""
    data = load_test_data(test_data_path)
    
    for doc_data in data["documents"]:
        # Convert datetime strings to datetime objects
        doc_data["created_at"] = datetime.fromisoformat(
            doc_data["created_at"].replace("Z", "+00:00")
        )
        doc_data["modified_at"] = datetime.fromisoformat(
            doc_data["modified_at"].replace("Z", "+00:00")
        )
        document = Document(**doc_data)
        test_db.add(document)
    
    test_db.commit()
    return data

@pytest.fixture
def mock_document_generator(monkeypatch):
    """Mock document generation functionality."""
    def mock_generate(*args, **kwargs):
        # Create temporary files for testing
        resume_fd, resume_path = tempfile.mkstemp(suffix=".pdf")
        cover_fd, cover_path = tempfile.mkstemp(suffix=".pdf")
        
        # Write some dummy content
        with open(resume_path, "w") as f:
            f.write("Mock Resume Content")
        with open(cover_path, "w") as f:
            f.write("Mock Cover Letter Content")
            
        return resume_path, cover_path
        
    monkeypatch.setattr(
        "jobsearch.features.document_generation.generator.generate_job_documents",
        mock_generate
    )

@pytest.mark.api
def test_generate_documents(client, test_jobs, test_documents, mock_document_generator, mock_gcs):
    """Test document generation endpoint."""
    generation_request = {
        "job_id": 1,
        "options": test_documents["generation_options"]
    }
    
    response = client.post("/api/documents/generate", json=generation_request)
    assert response.status_code == 200
    
    result = response.json()
    assert result["status"] == "completed"
    assert "resume_url" in result
    assert "cover_letter_url" in result
    assert isinstance(result["resume_id"], int)
    assert isinstance(result["cover_letter_id"], int)

@pytest.mark.api
def test_get_document(client, test_documents):
    """Test getting a single document."""
    response = client.get("/api/documents/1")
    assert response.status_code == 200
    
    doc = response.json()
    assert doc["id"] == 1
    assert doc["title"] == "Resume - TechCorp"
    assert doc["doc_type"] == "resume"
    assert "download_url" in doc

@pytest.mark.api
def test_get_nonexistent_document(client):
    """Test getting a document that doesn't exist."""
    response = client.get("/api/documents/999")
    assert response.status_code == 404

@pytest.mark.api
def test_list_documents(client, test_documents):
    """Test listing all documents."""
    response = client.get("/api/documents")
    assert response.status_code == 200
    
    docs = response.json()
    assert len(docs) == 2
    assert all("download_url" in doc for doc in docs)

@pytest.mark.api
def test_list_documents_with_filters(client, test_documents):
    """Test listing documents with filters."""
    # Test job_id filter
    response = client.get("/api/documents", params={"job_id": 1})
    assert response.status_code == 200
    docs = response.json()
    assert all(doc["job_id"] == 1 for doc in docs)
    
    # Test doc_type filter
    response = client.get("/api/documents", params={"doc_type": "resume"})
    assert response.status_code == 200
    docs = response.json()
    assert all(doc["doc_type"] == "resume" for doc in docs)
    
@pytest.mark.api
def test_generate_documents_invalid_job(client, mock_document_generator):
    """Test document generation with invalid job ID."""
    generation_request = {
        "job_id": 999,
        "options": {
            "template_name": "default",
            "use_visual_resume": True
        }
    }
    
    response = client.post("/api/documents/generate", json=generation_request)
    assert response.status_code == 404