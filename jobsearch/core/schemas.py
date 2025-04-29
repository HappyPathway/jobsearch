"""Core Pydantic models for structured outputs from LLM interactions.

This module defines Pydantic models used throughout the application for:
1. Type-safe AI responses
2. Standardized data structures
3. Input/output validation
4. Data exchange between components

These schemas ensure consistency in data format and validation across
the application, particularly when working with AI-generated content.

Example:
    ```python
    from jobsearch.core.ai import AIEngine
    from jobsearch.core.schemas import JobAnalysis
    
    ai_engine = AIEngine()
    analysis = await ai_engine.generate(
        prompt="Analyze this job posting: ...",
        output_type=JobAnalysis
    )
    match_score = analysis.match_score  # Strongly typed
    ```
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class LocationType(str, Enum):
    """Job location types.
    
    Attributes:
        REMOTE: Fully remote position
        HYBRID: Combination of remote and onsite work
        ONSITE: Requires physical presence at workplace
    """
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class CompanySize(str, Enum):
    """Company size categories.
    
    Attributes:
        STARTUP: Small, early-stage company (typically <50 employees)
        MIDSIZE: Medium-sized company (typically 50-500 employees)
        LARGE: Large company (typically 500-5000 employees)
        ENTERPRISE: Very large enterprise (typically >5000 employees)
    """
    STARTUP = "startup"
    MIDSIZE = "midsize"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class StabilityLevel(str, Enum):
    """Company stability assessment.
    
    Attributes:
        LOW: High risk, unstable (e.g., early startups, financial troubles)
        MEDIUM: Moderate stability (e.g., growing companies, some track record)
        HIGH: High stability (e.g., established companies, strong market position)
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GrowthPotential(str, Enum):
    """Career growth potential assessment.
    
    Attributes:
        LOW: Limited growth opportunities
        MEDIUM: Moderate growth opportunities
        HIGH: Excellent growth opportunities
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CompanyAnalysis(BaseModel):
    """Detailed analysis of a company from job posting and external data.
    
    This model contains information gathered from the job posting itself
    as well as external sources like Glassdoor, TechCrunch, and company websites.
    It provides context for job application decisions and strategy development.
    
    Attributes:
        industry: The industry sector of the company
        size: Company size category
        stability: Assessment of company financial/market stability
        glassdoor_rating: Optional Glassdoor rating (e.g., "4.2/5")
        employee_count: Optional employee count range
        year_founded: Optional year the company was founded
        growth_stage: Company growth stage (e.g., "Series B", "Public")
        market_position: Description of market position (e.g., "Leader", "Challenger")
        development_opportunities: List of career development opportunities at the company
    """
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
    """Complete analysis of a job posting.
    
    This model contains the AI analysis of a job posting, including assessment
    of match score, required skills, culture indicators, and growth potential.
    It's used to help job seekers evaluate opportunities and prioritize applications.
    
    Attributes:
        match_score: Percentage match between candidate and job (0-100)
        key_requirements: List of critical skills and requirements
        culture_indicators: Cultural aspects identified in the posting
        career_growth_potential: Assessment of growth opportunities
        total_years_experience: Total years of experience required
    """
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
