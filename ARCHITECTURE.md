# Career Automation Platform Architecture

## Repository Structure

```
jobsearch/
├── jobsearch/                 # Main package directory
│   ├── __init__.py
│   ├── features/             # Feature modules
│   │   ├── document_generation/
│   │   │   ├── __init__.py
│   │   │   ├── generator.py     # Document generation core functionality
│   │   │   └── templates/       # Document templates
│   │   ├── job_search/
│   │   │   ├── __init__.py
│   │   │   ├── search.py       # Job search functionality
│   │   │   └── analysis.py     # Job posting analysis
│   │   ├── strategy_generation/
│   │   │   ├── __init__.py
│   │   │   ├── generator.py    # Strategy generation logic
│   │   │   └── formatter.py    # Strategy output formatting
│   │   ├── profile_management/
│   │   │   ├── __init__.py
│   │   │   ├── scraper.py      # Profile data extraction
│   │   │   ├── resume_parser.py
│   │   │   └── cover_letter_parser.py
│   │   ├── web_presence/
│   │   │   ├── __init__.py
│   │   │   ├── github_pages.py # GitHub Pages generation
│   │   │   └── medium.py       # Medium article publishing
│   │   └── common/            # Shared utilities
│   │       ├── __init__.py
│   │       ├── logging.py
│   │       ├── storage.py
│   │       └── utils.py
│   └── core/                  # Core system components
│       ├── __init__.py
│       ├── ai.py              # AI/ML functionality
│       ├── database.py        # Database models and utilities
│       ├── logging.py         # Logging configuration
│       └── storage.py         # Storage interface
├── functions/                 # Cloud Functions
│   ├── document_generation/
│   ├── job_strategy/
│   ├── profile_update/
│   └── ...
├── tests/                     # Test suite
│   ├── unit/
│   │   ├── test_document_generation.py
│   │   ├── test_job_search.py
│   │   └── ...
│   └── integration/
├── config/                    # Configuration files
│   ├── gcs.json
│   └── ...
├── inputs/                    # Input document storage
│   ├── Profile.pdf
│   ├── Resume.pdf
│   └── CoverLetter.pdf
├── migrations/                # Database migrations
├── applications/             # Generated application materials
├── strategies/               # Generated strategies
└── pages/                    # Web presence content

```

## Feature Modules Overview

### 1. Document Generation (`features/document_generation/`)
- Handles creation of resumes and cover letters
- Contains document templates and generation logic
- Manages document storage and versioning

### 2. Job Search (`features/job_search/`)
- Implements job discovery and analysis
- Handles job matching and scoring
- Manages job data caching and updates

### 3. Strategy Generation (`features/strategy_generation/`)
- Creates daily and weekly job search strategies
- Generates actionable plans based on profile and job data
- Formats strategy output for different platforms

### 4. Profile Management (`features/profile_management/`)
- Manages professional profile data
- Parses and processes profile documents
- Maintains skill and experience tracking

### 5. Web Presence (`features/web_presence/`)
- Manages GitHub Pages professional site
- Handles Medium article publishing
- Maintains online professional presence

### 6. Common Utilities (`features/common/`)
- Shared logging functionality
- Storage utilities
- Common helper functions

## Core Components (`core/`)

### Database (`core/database.py`)
- SQLAlchemy models and database interface
- Data models for:
  - Professional experiences
  - Skills and certifications
  - Job applications
  - Target roles
  - Generated documents

### AI Integration (`core/ai.py`)
- Gemini API integration
- Structured prompting system
- AI-powered content generation

### Storage (`core/storage.py`)
- Google Cloud Storage integration
- Local file system management
- Document versioning and backup

### Logging (`core/logging.py`)
- Centralized logging configuration
- Log rotation and management
- Error tracking and reporting

## Cloud Functions (`functions/`)
Each cloud function is a self-contained module that implements specific platform functionality:
- Document generation
- Job strategy creation
- Profile updates
- Website deployment

## Configuration
- Environment variables through `.env`
- Google Cloud credentials
- API keys and service accounts
- Database configuration

## Testing
- Unit tests for each feature module
- Integration tests for workflows
- Mock data for testing
- CI/CD test automation

## Best Practices
1. Keep feature modules isolated and focused
2. Use dependency injection for services
3. Maintain consistent logging across modules
4. Document all public interfaces
5. Write tests for new functionality
6. Follow Python type hinting
7. Keep configuration separate from code

## Development Workflow
1. Create feature branch
2. Implement changes in appropriate module
3. Update tests and documentation
4. Run test suite
5. Submit pull request
6. Deploy after review

## Deployment
- Cloud Functions deploy through GitHub Actions
- Database migrations run automatically
- Configuration managed through Cloud Secret Manager
- Monitoring through Cloud Logging