# Job Search Automation Platform API Design

## Overview

This document outlines the REST API design for the Job Search Automation Platform. The API will be implemented using FastAPI and will provide programmatic access to all core features of the platform including job search, profile management, document generation, and strategy creation.

## API Structure

```
jobsearch-api/
├── app/
│   ├── main.py               # FastAPI application entry point
│   ├── dependencies.py       # Shared dependencies (DB session, etc.)
│   ├── models/               # Pydantic models for API requests/responses
│   ├── routers/              # API route modules
│   └── services/             # Business logic adapters to existing codebase
```

## Authentication

API endpoints will be secured using OAuth2 with JWT tokens. Non-authenticated users will have limited read-only access.

## Endpoints

### Jobs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs/search` | GET | Search for jobs based on query parameters |
| `/api/jobs/{job_id}` | GET | Get details for a specific job |
| `/api/jobs/{job_id}/analysis` | GET | Get detailed job analysis |
| `/api/jobs/{job_id}/apply` | POST | Mark a job as applied with optional notes |
| `/api/jobs/tracked` | GET | List all tracked jobs |
| `/api/jobs/priority` | GET | List jobs by priority |

### Profile Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/profile/summary` | GET | Get consolidated profile summary |
| `/api/profile/skills` | GET | Get all skills in the user's profile |
| `/api/profile/skills` | POST | Add new skills to profile |
| `/api/profile/experiences` | GET | List professional experiences |
| `/api/profile/experiences` | POST | Add new experience |
| `/api/profile/upload/resume` | POST | Upload and parse a resume PDF |
| `/api/profile/upload/cover-letter` | POST | Upload and parse a cover letter PDF |

### Document Generation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/documents/generate` | POST | Generate tailored resume and cover letter |
| `/api/documents/list` | GET | List all generated documents |
| `/api/documents/{document_id}` | GET | Get specific document metadata |
| `/api/documents/{document_id}/download` | GET | Download document file |
| `/api/documents/templates` | GET | List available document templates |
| `/api/documents/validate` | POST | Validate document content |

### Strategy Generation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/strategies/generate` | POST | Generate a job search strategy |
| `/api/strategies/latest` | GET | Get the most recent strategy |
| `/api/strategies/{date}` | GET | Get strategy for specific date |
| `/api/strategies/weekly` | GET | Get weekly strategy focus |

### Web Presence

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/web-presence/github-pages` | POST | Update GitHub Pages site |
| `/api/web-presence/medium` | POST | Generate Medium article draft |
| `/api/web-presence/settings` | GET | Get web presence settings |
| `/api/web-presence/settings` | PUT | Update web presence settings |

## Data Models

### Job Models

```python
class JobBase(BaseModel):
    title: str
    company: str
    description: str
    url: HttpUrl
    
class JobCreate(JobBase):
    location: Optional[str] = None
    post_date: Optional[str] = None
    match_score: Optional[float] = None
    application_priority: Optional[str] = "medium"
    key_requirements: Optional[List[str]] = []
    
class JobResponse(JobBase):
    id: int
    match_score: float
    application_priority: str
    key_requirements: List[str]
    career_growth_potential: Optional[str]
    
class JobApplicationStatus(BaseModel):
    status: str
    notes: Optional[str] = None
    resume_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
```

### Profile Models

```python
class SkillBase(BaseModel):
    name: str
    proficiency: Optional[str] = None
    
class SkillResponse(SkillBase):
    id: int
    
class ExperienceBase(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: Optional[str] = None
    description: str
    
class ExperienceResponse(ExperienceBase):
    id: int
    skills: List[str]
    
class ProfileResponse(BaseModel):
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    location: Optional[str]
    summary: str
    experiences: List[ExperienceResponse]
    skills: List[SkillResponse]
    target_roles: List[str]
```

### Strategy Models

```python
class StrategyGenerate(BaseModel):
    include_weekly_focus: bool = True
    job_limit: int = 10
    
class StrategyResponse(BaseModel):
    date: str
    content: str
    daily_focus: Dict[str, Any]
    jobs: List[JobResponse]
    weekly_focus: Optional[str] = None
```

### Document Models

```python
class DocumentGenerate(BaseModel):
    job_id: int
    use_writing_pass: bool = True
    use_visual_resume: bool = True
    
class DocumentResponse(BaseModel):
    job: JobResponse
    resume_path: str
    cover_letter_path: str
    created_at: datetime
    success: bool
    visual_resume_path: Optional[str] = None
    ats_resume_path: Optional[str] = None
```

## Integration with Existing Code

The API will integrate with the existing codebase by:

1. Using the existing database models/session management
2. Creating service adapters that call into existing functionality
3. Maintaining the same storage mechanisms (GCS)
4. Preserving all business logic

This approach ensures the API is a thin layer on top of the existing robust functionality.

## Deployment Options

1. **Docker Container**: Package API with all dependencies
2. **Cloud Run**: Deploy as a scalable serverless container
3. **Google Cloud Functions**: For lightweight endpoints
4. **Local Development**: Run alongside existing code for testing

## Implementation Plan

1. Set up FastAPI framework with dependency injection
2. Implement core data models (Pydantic schemas)
3. Create route handlers with existing functionality
4. Add authentication and permissions
5. Set up automated testing
6. Deploy as Docker container
7. Create client examples (Python, JavaScript)

## API Versioning

API will use URI versioning: `/api/v1/...` to allow for future changes while maintaining backward compatibility.