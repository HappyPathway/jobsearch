"""Job-related models."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class JobBase(BaseModel):
    """Base job model."""
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    url: str

class JobCreate(JobBase):
    """Job creation model."""
    pass

class JobResponse(JobBase):
    """Job response model."""
    id: int
    first_seen_date: Optional[str] = None
    last_seen_date: Optional[str] = None
    match_score: Optional[float] = None
    application_status: Optional[str] = None
    
    class Config:
        from_attributes = True

class JobSearchParams(BaseModel):
    """Job search parameters."""
    keywords: str
    location: Optional[str] = None
    remote_only: Optional[bool] = False

class JobApplicationStatus(BaseModel):
    """Job application status response."""
    application_id: int
    status: str
    submitted_at: str
    resume_url: Optional[str] = None
    cover_letter_url: Optional[str] = None
