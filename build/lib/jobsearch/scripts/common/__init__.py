"""Common utilities shared across script implementations."""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class JobInfo:
    """Information about a job posting."""
    url: str
    title: str
    company: str
    description: str
    location: str
    post_date: Optional[str] = None
    match_score: Optional[float] = None
    key_requirements: Optional[List[str]] = None
    culture_indicators: Optional[List[str]] = None
    career_growth_potential: Optional[str] = None
    
@dataclass
class ProfileData:
    """Structured profile information."""
    experiences: List[Dict]
    skills: List[str]
    target_roles: List[Dict]

def get_today() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")

def clean_file_path(path: str) -> str:
    """Clean a string for use in a file path."""
    return "".join(c for c in path if c.isalnum() or c in "._- ")