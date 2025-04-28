"""Profile-related models."""
from typing import Optional, List
from pydantic import BaseModel

class SkillBase(BaseModel):
    """Base skill model."""
    name: str
    proficiency: Optional[str] = None
    years_experience: Optional[float] = None
    categories: Optional[List[str]] = None

class SkillCreate(SkillBase):
    """Skill creation model."""
    pass

class SkillResponse(SkillBase):
    """Skill response model."""
    id: int
    
    class Config:
        from_attributes = True

class ExperienceBase(BaseModel):
    """Base experience model."""
    company: str
    title: str
    start_date: str
    end_date: Optional[str] = None
    description: Optional[str] = None
    highlights: Optional[List[str]] = None

class ExperienceCreate(ExperienceBase):
    """Experience creation model."""
    skills: List[str] = []

class ExperienceResponse(ExperienceBase):
    """Experience response model."""
    id: int
    skills: List[SkillResponse] = []
    
    class Config:
        from_attributes = True

class ProfileSummary(BaseModel):
    """Profile summary model."""
    full_name: Optional[str] = None
    target_roles: List[str]
    top_skills: List[SkillResponse]
    recent_experiences: List[ExperienceResponse]

class ProfileUpdate(BaseModel):
    """Profile update model."""
    target_roles: Optional[List[str]] = None
