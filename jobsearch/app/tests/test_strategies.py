"""Tests for job search strategy endpoints."""
import json
from pathlib import Path
import pytest
from datetime import datetime, date

def load_test_data(test_data_path):
    """Load test strategy data from JSON file."""
    with open(test_data_path / "strategies.json") as f:
        return json.load(f)

@pytest.fixture
def mock_strategy_generator(monkeypatch):
    """Mock strategy generation functionality."""
    def mock_generate(job_limit=None, include_recruiters=False, generate_documents=False):
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "job_recommendations": [
                {
                    "job_id": 1,
                    "title": "Senior Software Engineer",
                    "company": "TechCorp",
                    "match_score": 0.85,
                    "priority": "high",
                    "action_items": [
                        "Update resume with recent cloud projects",
                        "Prepare system design examples"
                    ]
                }
            ],
            "next_steps": [
                "Focus on cloud-native positions",
                "Highlight team leadership experience"
            ],
            "skills_to_develop": [
                {
                    "skill": "AWS Advanced Networking",
                    "priority": "high",
                    "resources": ["AWS certification course"]
                }
            ],
            "weekly_goals": {
                "applications": job_limit or 5,
                "networking_events": 2,
                "technical_articles": 1
            }
        }
        return data

    monkeypatch.setattr(
        "jobsearch.features.strategy_generation.generator.generate_strategy",
        mock_generate
    )
    return mock_generate

@pytest.mark.api
def test_generate_strategy(client, mock_strategy_generator):
    """Test strategy generation endpoint."""
    response = client.post(
        "/api/strategies/generate",
        params={
            "job_limit": 5,
            "include_recruiters": False,
            "generate_docs": False
        }
    )
    assert response.status_code == 200
    
    result = response.json()
    assert result["status"] == "success"
    assert "strategy" in result
    assert "generated_at" in result
    
    strategy = result["strategy"]
    assert "job_recommendations" in strategy
    assert "next_steps" in strategy
    assert "skills_to_develop" in strategy
    assert "weekly_goals" in strategy
    
    # Verify weekly goals match input parameters
    assert strategy["weekly_goals"]["applications"] == 5

@pytest.mark.api
def test_get_latest_strategy(client, mock_strategy_generator):
    """Test getting the latest strategy."""
    # First generate a strategy
    client.post("/api/strategies/generate")
    
    # Now get the latest
    response = client.get("/api/strategies/latest")
    assert response.status_code == 200
    
    strategy = response.json()
    assert "job_recommendations" in strategy
    assert "next_steps" in strategy
    assert "skills_to_develop" in strategy
    assert "weekly_goals" in strategy

@pytest.mark.api
def test_get_strategy_by_date(client, mock_strategy_generator):
    """Test getting a strategy by date."""
    # Generate a strategy first
    client.post("/api/strategies/generate")
    
    # Get strategy for today
    today = date.today().isoformat()
    response = client.get(f"/api/strategies/by-date/{today}")
    assert response.status_code == 200
    
    strategy = response.json()
    assert "job_recommendations" in strategy
    assert "next_steps" in strategy
    assert "skills_to_develop" in strategy
    assert "weekly_goals" in strategy

@pytest.mark.api
def test_get_nonexistent_strategy(client):
    """Test getting a strategy for a date with no strategy."""
    future_date = "2026-01-01"
    response = client.get(f"/api/strategies/by-date/{future_date}")
    assert response.status_code == 404

@pytest.mark.api
def test_generate_strategy_with_documents(client, mock_strategy_generator, mock_document_generator):
    """Test strategy generation with document generation enabled."""
    response = client.post(
        "/api/strategies/generate",
        params={
            "job_limit": 3,
            "include_recruiters": True,
            "generate_docs": True
        }
    )
    assert response.status_code == 200
    
    result = response.json()
    assert result["status"] == "success"
    assert "strategy" in result
    
    strategy = result["strategy"]
    assert len(strategy["job_recommendations"]) <= 3  # Respects job limit