from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class SkillBase(BaseModel):
    name: str
    proficiency: Optional[str] = "intermediate"
    years_experience: Optional[float] = 0.0
    categories: Optional[List[str]] = []

class SkillCreate(SkillBase):
    pass

class SkillResponse(SkillBase):
    id: int
    
    class Config:
        from_attributes = True

class ExperienceBase(BaseModel):
    company: str
    title: str
    start_date: date
    end_date: Optional[date] = None
    description: str
    highlights: List[str] = []
    skills: List[str] = []

class ExperienceCreate(ExperienceBase):
    pass

class ExperienceResponse(ExperienceBase):
    id: int
    skills: List[SkillResponse]
    
    class Config:
        from_attributes = True

class ProfileSummary(BaseModel):
    full_name: Optional[str]
    target_roles: List[str]
    top_skills: List[SkillResponse]
    recent_experiences: List[ExperienceResponse]
    highlight_projects: Optional[List[str]] = []
    career_objectives: Optional[List[str]] = []
    
    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    target_roles: Optional[List[str]] = None
    career_objectives: Optional[List[str]] = None
    full_name: Optional[str] = None