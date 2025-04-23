"""Tests for job search endpoints."""
import json
from pathlib import Path
import pytest
from datetime import datetime, timezone

from jobsearch.core.models import JobCache, JobApplication


def load_test_data(test_data_path):
    """Load test job data from JSON file."""
    with open(test_data_path / "jobs.json") as f:
        return json.load(f)

@pytest.fixture
def test_jobs(test_data_path, test_db):
    """Insert test jobs into database."""
    data = load_test_data(test_data_path)
    
    # Add jobs
    for job_data in data["jobs"]:
        job = JobCache(**job_data)
        test_db.add(job)
    
    # Add applications
    for app_data in data["applications"]:
        app_data["application_date"] = datetime.fromisoformat(
            app_data["application_date"].replace("Z", "+00:00")
        )
        application = JobApplication(**app_data)
        test_db.add(application)
    
    test_db.commit()
    return data

@pytest.mark.api
def test_search_jobs(client, test_jobs):
    """Test job search endpoint."""
    response = client.get(
        "/api/jobs/search",
        params={
            "keywords": "engineer",
            "location": "San Francisco",
            "remote_only": False,
            "min_match_score": 0.7
        }
    )
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) > 0
    assert jobs[0]["title"] == "Senior Software Engineer"
    assert jobs[0]["company"] == "TechCorp"

@pytest.mark.api
def test_get_job(client, test_jobs):
    """Test get single job endpoint."""
    response = client.get("/api/jobs/1")
    assert response.status_code == 200
    job = response.json()
    assert job["id"] == 1
    assert job["title"] == "Senior Software Engineer"
    assert job["match_score"] == 0.85

@pytest.mark.api
def test_get_nonexistent_job(client):
    """Test getting a job that doesn't exist."""
    response = client.get("/api/jobs/999")
    assert response.status_code == 404

@pytest.mark.api
def test_mark_job_applied(client, test_jobs):
    """Test marking a job as applied."""
    application_data = {
        "status": "applied",
        "notes": "Applied via company website",
        "resume_path": "resumes/test_resume.pdf",
        "cover_letter_path": "cover_letters/test_cover.pdf"
    }
    response = client.post(
        "/api/jobs/2/apply",
        json=application_data
    )
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "applied"
    assert result["job_id"] == 2

@pytest.mark.api
def test_get_applications(client, test_jobs):
    """Test getting list of job applications."""
    response = client.get("/api/jobs/applications")
    assert response.status_code == 200
    applications = response.json()
    assert len(applications) == 1
    assert applications[0]["job_id"] == 1
    assert applications[0]["status"] == "applied"

@pytest.mark.api
def test_get_applications_with_status_filter(client, test_jobs):
    """Test getting applications filtered by status."""
    response = client.get(
        "/api/jobs/applications",
        params={"status": "applied"}
    )
    assert response.status_code == 200
    applications = response.json()
    assert all(app["status"] == "applied" for app in applications)