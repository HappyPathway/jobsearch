"""Core Pydantic models for structured outputs from LLM interactions."""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class LocationType(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class CompanySize(str, Enum):
    STARTUP = "startup"
    MIDSIZE = "midsize"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class StabilityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GrowthPotential(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CompanyAnalysis(BaseModel):
    """Detailed analysis of a company from job posting and external data."""
    industry: str
    size: CompanySize
    stability: StabilityLevel
    glassdoor_rating: Optional[str] = None
    employee_count: Optional[str] = None
    year_founded: Optional[str] = None
    growth_stage: str
    market_position: str
    development_opportunities: List[str]


class JobAnalysis(BaseModel):
    """Complete analysis of a job posting."""
    match_score: float = Field(..., ge=0, le=100)
    key_requirements: List[str]
    culture_indicators: List[str]
    career_growth_potential: GrowthPotential
    total_years_experience: int = Field(..., ge=0)
    candidate_gaps: List[str]
    location_type: LocationType
    company_size: CompanySize
    company_stability: StabilityLevel
    development_opportunities: List[str]
    reasoning: str


class ResumeSection(BaseModel):
    """Section of a resume with title and content."""
    title: str
    content: List[str]
    priority: Optional[int] = None


class ResumeContent(BaseModel):
    """Complete structured resume content."""
    contact_info: dict
    summary: str
    experience: List[ResumeSection]
    skills: List[str]
    education: List[ResumeSection]
    additional_sections: Optional[List[ResumeSection]] = None


class CoverLetterSection(BaseModel):
    """Section of a cover letter."""
    type: str  # intro, body, closing
    content: str
    key_points: List[str]


class CoverLetterContent(BaseModel):
    """Complete structured cover letter content."""
    greeting: str
    introduction: CoverLetterSection
    body_sections: List[CoverLetterSection]
    closing: CoverLetterSection
    signature: str


class ArticleSection(BaseModel):
    """Section of a technical article."""
    heading: str
    content: List[str]
    key_points: List[str]
    code_examples: Optional[List[str]] = None


class Article(BaseModel):
    """Complete structured article content."""
    title: str
    introduction: str
    sections: List[ArticleSection]
    tags: List[str]


class FocusArea(BaseModel):
    """Daily job search focus area."""
    primary_goal: str
    secondary_goals: List[str]


class NetworkingTarget(BaseModel):
    """Networking target for job search."""
    role: str
    company: str
    connection_strategy: str


class ActionItem(BaseModel):
    """Specific action item in job search strategy."""
    description: str
    priority: str
    deadline: str
    metrics: List[str]


class DailyStrategy(BaseModel):
    """Complete daily job search strategy."""
    daily_focus: FocusArea
    target_companies: List[str]
    networking_targets: List[NetworkingTarget]
    action_items: List[ActionItem]


class GithubPagesSummary(BaseModel):
    """Professional summary for GitHub Pages."""
    headline: str
    summary: List[str]
    key_points: List[str]
    target_roles: List[str]


class ProfessionalSummary(BaseModel):
    """Detailed professional summary."""
    headline: str
    summary: List[str]
    key_points: List[str]


class Tagline(BaseModel):
    """Professional tagline."""
    tagline: str
