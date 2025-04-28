from enum import Enum
from pydantic import BaseModel
from typing import Any, Optional, List

class JobApplicationStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"

class JobBase(BaseModel):
    title: str
    company: str
    location: str
    description: str
    url: Optional[str] = None

class JobCreate(JobBase):
    status: Optional[JobApplicationStatus] = JobApplicationStatus.PENDING

class JobResponse(JobBase):
    id: int
    status: JobApplicationStatus
    extra: Optional[dict[str, Any]] = None

class JobSearchParams(BaseModel):
    keywords: str
    location: Optional[str] = None
    remote_only: bool = False
    limit: int = 10

__all__ = [
    'JobApplicationStatus',
    'JobBase',
    'JobCreate',
    'JobResponse',
    'JobSearchParams'
]
