"""Tests for web presence management endpoints."""
import json
from pathlib import Path
import pytest
from datetime import datetime

def load_test_data(test_data_path):
    """Load test web presence data from JSON file."""
    with open(test_data_path / "web_presence.json") as f:
        return json.load(f)

@pytest.fixture
def mock_pages_generator(monkeypatch):
    """Mock GitHub Pages generation."""
    def mock_generate():
        return True
    monkeypatch.setattr(
        "jobsearch.features.web_presence.github_pages.generate_pages",
        mock_generate
    )
    return mock_generate

@pytest.fixture
def mock_article_generator(monkeypatch):
    """Mock Medium article generation."""
    def mock_generate(job_ids, preview=True):
        if preview:
            return "Preview of article content..."
        else:
            return {
                "title": "New Job Opportunities in Tech",
                "url": "https://medium.com/@username/new-article",
                "published_at": datetime.utcnow().isoformat()
            }
    monkeypatch.setattr(
        "jobsearch.features.web_presence.medium.generate_article",
        mock_generate
    )
    return mock_generate

@pytest.mark.api
def test_generate_github_pages(client, mock_pages_generator):
    """Test GitHub Pages generation endpoint."""
    response = client.post("/api/web-presence/github-pages/generate")
    assert response.status_code == 200
    
    result = response.json()
    assert result["status"] == "started"
    assert "message" in result

@pytest.mark.api
def test_create_medium_article_preview(client, test_jobs, mock_article_generator):
    """Test Medium article generation in preview mode."""
    request_data = {
        "job_ids": [1, 2],
        "preview_only": True
    }
    
    response = client.post(
        "/api/web-presence/medium/article",
        json=request_data
    )
    assert response.status_code == 200
    
    result = response.json()
    assert result["status"] == "preview"
    assert "content" in result
    assert isinstance(result["content"], str)

@pytest.mark.api
def test_publish_medium_article(client, test_jobs, mock_article_generator):
    """Test Medium article publishing."""
    request_data = {
        "job_ids": [1, 2],
        "preview_only": False
    }
    
    response = client.post(
        "/api/web-presence/medium/article",
        json=request_data
    )
    assert response.status_code == 200
    
    result = response.json()
    assert result["status"] == "publishing"
    assert "message" in result

@pytest.mark.api
def test_create_medium_article_invalid_jobs(client, mock_article_generator):
    """Test Medium article generation with invalid job IDs."""
    request_data = {
        "job_ids": [999, 1000],
        "preview_only": True
    }
    
    response = client.post(
        "/api/web-presence/medium/article",
        json=request_data
    )
    assert response.status_code == 404