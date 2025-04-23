from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime

class JobBase(BaseModel):
    title: str
    company: str
    description: str
    url: HttpUrl
    
class JobCreate(JobBase):
    location: Optional[str] = None
    post_date: Optional[datetime] = None
    match_score: Optional[float] = None
    application_priority: Optional[str] = "medium"
    key_requirements: Optional[List[str]] = []
    
class JobResponse(JobBase):
    id: int
    location: Optional[str] = None
    match_score: float
    application_priority: str
    key_requirements: List[str]
    career_growth_potential: Optional[str] = None
    
    class Config:
        from_attributes = True

class JobSearchParams(BaseModel):
    keywords: str
    location: Optional[str] = None
    remote_only: Optional[bool] = False
    min_match_score: Optional[float] = 0.0
    limit: Optional[int] = 10
    
class JobApplicationStatus(BaseModel):
    status: str
    notes: Optional[str] = None
    resume_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
    application_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True