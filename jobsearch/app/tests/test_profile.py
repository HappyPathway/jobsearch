"""Tests for profile management endpoints."""
import json
from pathlib import Path
import pytest
from datetime import date
import io

from jobsearch.core.models import Skill, Experience

def load_test_data(test_data_path):
    """Load test profile data from JSON file."""
    with open(test_data_path / "profiles.json") as f:
        return json.load(f)

@pytest.fixture
def test_profiles(test_data_path, test_db):
    """Insert test profile data into database."""
    data = load_test_data(test_data_path)
    
    # Add skills
    for skill_data in data["skills"]:
        skill = Skill(**skill_data)
        test_db.add(skill)
    
    # Add experiences
    for exp_data in data["experiences"]:
        exp_data["start_date"] = date.fromisoformat(exp_data["start_date"])
        if exp_data["end_date"]:
            exp_data["end_date"] = date.fromisoformat(exp_data["end_date"])
            
        # Remove skills temporarily
        skills = exp_data.pop("skills")
        experience = Experience(**exp_data)
        
        # Add skills back as relationships
        for skill_name in skills:
            skill = test_db.query(Skill).filter(Skill.name == skill_name).first()
            if skill:
                experience.skills.append(skill)
        
        test_db.add(experience)
    
    test_db.commit()
    return data

@pytest.mark.api
def test_get_profile_summary(client, test_profiles):
    """Test getting profile summary."""
    response = client.get("/api/profile/summary")
    assert response.status_code == 200
    
    summary = response.json()
    assert summary["full_name"] is not None
    assert len(summary["target_roles"]) > 0
    assert len(summary["top_skills"]) > 0
    assert len(summary["recent_experiences"]) > 0

@pytest.mark.api
def test_create_skill(client):
    """Test creating a new skill."""
    skill_data = {
        "name": "TypeScript",
        "proficiency": "advanced",
        "years_experience": 2.5,
        "categories": ["Programming Languages", "Frontend Development"]
    }
    
    response = client.post("/api/profile/skills", json=skill_data)
    assert response.status_code == 200
    
    created_skill = response.json()
    assert created_skill["name"] == "TypeScript"
    assert created_skill["proficiency"] == "advanced"
    assert isinstance(created_skill["id"], int)

@pytest.mark.api
def test_list_skills(client, test_profiles):
    """Test listing all skills."""
    response = client.get("/api/profile/skills")
    assert response.status_code == 200
    
    skills = response.json()
    assert len(skills) == 3
    assert any(s["name"] == "Python" for s in skills)

@pytest.mark.api
def test_create_experience(client, test_profiles):
    """Test creating a new experience entry."""
    experience_data = {
        "company": "NewTech Solutions",
        "title": "Technical Lead",
        "start_date": "2025-01-01",
        "description": "Leading technical initiatives...",
        "highlights": ["Launched new platform", "Grew team to 10 engineers"],
        "skills": ["Python", "Cloud Infrastructure"]
    }
    
    response = client.post("/api/profile/experiences", json=experience_data)
    assert response.status_code == 200
    
    created_exp = response.json()
    assert created_exp["company"] == "NewTech Solutions"
    assert created_exp["title"] == "Technical Lead"
    assert len(created_exp["skills"]) == 2

@pytest.mark.api
def test_list_experiences(client, test_profiles):
    """Test listing all experiences."""
    response = client.get("/api/profile/experiences")
    assert response.status_code == 200
    
    experiences = response.json()
    assert len(experiences) == 2
    assert all("skills" in exp for exp in experiences)

@pytest.mark.api
def test_upload_resume(client, mock_gcs):
    """Test uploading and parsing a resume."""
    # Create a mock PDF file
    mock_pdf_content = b"Mock PDF content for testing"
    mock_pdf = io.BytesIO(mock_pdf_content)
    
    files = {
        "file": ("resume.pdf", mock_pdf, "application/pdf")
    }
    
    response = client.post(
        "/api/profile/upload/resume",
        files=files
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify the file was "uploaded" to mock GCS
    assert "resumes/resume.pdf" in mock_gcs.files