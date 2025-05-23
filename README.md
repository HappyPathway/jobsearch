# 🚀 Career Automation Platform

**Transform your job search into a strategic advantage.**

Ever felt overwhelmed managing application documents, tracking opportunities, and staying on top of your job search? This AI-powered platform makes your career journey smarter, more organized, and far more effective.

---

## 🌟 Why This Platform Changes Everything

Job searching traditionally feels like throwing résumés into a void and hoping for the best. Not anymore:

- **AI-Powered Analysis:** Your profile data is analyzed to match you with ideal opportunities
- **Strategic Daily Focus:** Get personalized job search plans based on real-time market data
- **Dynamic Document Generation:** Create perfectly tailored résumés and cover letters in seconds
- **Professional Web Presence:** Automatically maintain your career website on GitHub Pages
- **Complete Application Tracking:** Never lose sight of where you've applied and what's next
- **Persistent Cloud Storage:** Your data stays safe and accessible from anywhere

---

## 🏃‍♂️ Quick Start

### Prerequisites
- Python 3.11+
- Git
- GitHub account
- Google Gemini API key
- Google Cloud Project access

### Environment Setup
1. Copy the environment template: `cp .env.example .env`
2. Update the `.env` file with your configuration
3. For production, use Google Secret Manager for sensitive values:
   ```bash
   # Store a secret
   gcloud secrets create SECRET_NAME --data-file=/path/to/secret

   # Access in code
   from jobsearch.core.secrets import secret_manager
   value = secret_manager.get_secret('SECRET_NAME')
   ```

### Setup in 6 Easy Steps
1. **Clone your repo:** Use this template and clone it locally
2. **Set up Google Cloud:** Ensure you have proper credentials (the system creates a bucket automatically)
3. **Install dependencies:** `make install`
4. **Add your documents:** Place your résumé, cover letter and profile in the `docs/` directory
5. **Configure secrets:** Add API keys to `.env` and GitHub secrets
6. **Initialize:** Run `gh workflow run system-init.yml`

For a detailed understanding of the system architecture and organization, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 🧩 System Architecture: How Everything Fits Together

This platform uses a modular architecture where specialized Python scripts interact with a central SQLite database, which is backed up to Google Cloud Storage. Here's how the system components work together:

### Data Flow Architecture
```mermaid
graph TD
    A[Your Documents] --> B[Document Parsers]
    B --> C[SQLite Database]
    D[Online Job Sources] --> E[Job Search & Analysis]
    E --> C
    C --> F[Strategy Generation]
    C --> G[Document Generation]
    C --> H[GitHub Pages Site]
    C <--> I[Google Cloud Storage]
```

### Core Components

#### 1. The Database: Your Career Command Center
The SQLite database (synced to Google Cloud) maintains relationships between:

- Your professional **Experiences** and **Skills** (many-to-many)
- **Target Roles** you're pursuing
- **Job Postings** you've discovered
- **Applications** you've submitted
- **Recruiter Contacts** you've made

#### 2. Data Processing Pipeline

1. **Import Phase**
   - **Document Parsing:** Your résumé, cover letter, and profile are parsed into structured data
   - **Profile Building:** The system creates a comprehensive understanding of your career
   
2. **Job Search Phase**
   - **Discovery:** The system finds relevant job postings
   - **Analysis:** AI evaluates job fit based on your profile
   - **Prioritization:** Positions are scored and ranked
   
3. **Execution Phase**
   - **Strategy Creation:** Daily job search focus areas are generated
   - **Document Generation:** Custom résumés and cover letters are created
   - **Application Tracking:** Your application status is maintained
   - **Web Presence:** Your professional site is kept updated

---

## 🔄 Daily Workflow

Here's how to make the most of this platform every day:

1. **Morning Briefing:** Run `make daily-workflow` to get your personalized strategy and application materials
2. **Apply to Jobs:** Follow your strategy recommendations for that day
3. **Track Progress:** Mark jobs as applied using `make mark-applied URL="job_url"`
4. **End of Day Sync:** Run `make sync-and-publish` to update your data and website

---

## 🛠️ How It Really Works: A Technical Overview

### The Data Model

The system uses SQLAlchemy models to structure your career data:

```python
# Core career data models
Experience <---> Skill  # Many-to-many relationship
TargetRole              # Career targets with match scores
ResumeSection           # Structured résumé content
CoverLetterSection      # Structured cover letter content

# Job search models
JobCache <---> JobApplication  # One-to-many relationship  
RecruiterContact              # Networking contacts
```

#### Key Model Relationships

The **Experience** and **Skill** tables form the foundation of your professional profile through a many-to-many relationship. Each job posting in **JobCache** can have multiple **JobApplication** records, tracking different application attempts or statuses.

### The Script Pipeline

Each script has a specific role in the data flow:

1. **Data Import Scripts**
   - `profile_scraper.py`: Pulls data from LinkedIn or similar sources
   - `resume_parser.py`: Extracts structured data from your résumé PDF
   - `cover_letter_parser.py`: Parses your cover letter style and content
   
2. **Data Integration Scripts**
   - `combine_and_summarize.py`: Creates a unified profile from all sources
   
3. **Job Discovery and Analysis**
   - `job_search.py`: Finds new relevant positions online
   - `job_analysis.py`: Uses AI to score jobs against your profile
   
4. **Strategy and Document Generation**
   - `strategy_generator.py`: Creates daily job search recommendations
   - `document_generator.py`: Builds tailored application materials
   
5. **Tracking and Publishing**
   - `mark_job_applied.py`: Records your application activities
   - `generate_github_pages.py`: Updates your online presence
   
6. **Infrastructure Support**
   - `gcs_utils.py`: Handles cloud storage synchronization
   - `init_db.py`: Maintains database schema
   - Various utility scripts for logging, formatting, etc.

### How Scripts Use the Models

When you run a script like `strategy_generator.py`, it:
1. Opens a database session through the SQLAlchemy ORM
2. Queries relevant models (Experiences, Skills, JobCache entries)
3. Processes the data (often using AI via Gemini API)
4. Creates or updates records in the database
5. Commits the changes and syncs to Google Cloud

---

## 📊 Project Status

### ✅ Working Components

**Core Data Management**
- ✅ SQLite database with GCS sync
- ✅ SQLAlchemy ORM models
- ✅ Automated migrations
- ✅ Data validation with Pydantic

**Profile Management**
- ✅ LinkedIn profile scraping
- ✅ Resume parsing
- ✅ Cover letter analysis
- ✅ Skills extraction
- ⚠️ Non-standard PDF parsing

**Job Search**
- ✅ Automated job discovery
- ✅ Job analysis with Gemini
- ✅ Match scoring
- ✅ Application tracking

**Document Generation**
- ✅ Dynamic resume creation
- ✅ Cover letter customization
- ✅ ATS optimization
- ✅ Multiple output formats

**Infrastructure**
- ✅ GCS synchronization
- ✅ GitHub Actions automation
- ✅ Slack integration
- ✅ Error tracking

### 🚧 Known Issues

**Strategy Generation**
- Integration test failures in job strategy workflow
- Occasional timeouts during generation
- Weekly focus calculation needs refinement

**Profile Management**
- PDF parsing inconsistencies
- Skills categorization improvements needed
- Experience date formatting issues

### 🎯 Next Steps

**Immediate Priorities**
1. Fix strategy generation test failures
2. Improve PDF parsing resilience
3. Update API documentation

**Short-term Goals**
1. Enhance skills categorization
2. Optimize job matching algorithm
3. Add more test coverage

**Long-term Plans**
1. Implement machine learning for job matching
2. Add career path prediction
3. Integrate more job sources

---

## 🔍 Daily Usage Examples

### Example 1: Morning Job Search Routine
```bash
# Generate today's job search strategy and documents
make daily-workflow
```

This command:
1. Updates local database from Google Cloud
2. Searches for new jobs matching your profile
3. Analyzes and scores each position
4. Generates a daily strategy document
5. Creates customized résumé and cover letter for priority jobs
6. Updates your GitHub Pages website
7. Syncs everything back to Google Cloud

### Example 2: Tracking an Application
```bash
# Mark a job as applied with notes
make mark-applied URL="https://example.com/job" STATUS="applied" NOTES="Spoke with recruiter Jane"
```

This updates the JobApplication record and maintains your application history.

---

## 🧠 Under the Hood: Technical Deep Dive

### Complete Database Schema

```
Experience (id, company, title, start_date, end_date, description)
  ↓ ↑
experience_skills (experience_id, skill_id)
  ↑ ↓
Skill (id, skill_name)

TargetRole (id, role_name, priority, match_score, reasoning, source, last_updated)

ResumeSection (id, section_name, content)
ResumeExperience (id, company, title, start_date, end_date, location, description)
ResumeEducation (id, institution, degree, field, graduation_date, gpa)

CoverLetterSection (id, section_name, content)

JobCache (id, url, title, company, description, dates, match_score, priority, requirements, ...)
  ↓
JobApplication (id, job_cache_id, application_date, status, resume_path, cover_letter_path, notes)

RecruiterContact (id, name, title, company, url, source, dates, status, notes)
```

### Key SQL Relationships

The system maintains these critical relationships in the database:

1. **Experience-to-Skill**: A many-to-many relationship connecting your work history to your skills
2. **JobCache-to-JobApplication**: A one-to-many relationship tracking all interactions with a job posting
3. **Related tables**: Connected through foreign keys and queries to build a complete picture of your career

### Cloud Storage Integration

All local database changes are automatically synced to Google Cloud Storage:

1. Local modifications are committed to SQLite
2. The database file is uploaded to GCS 
3. When scripts run, they first fetch the latest database
4. This ensures consistency across environments and devices

---

## 🛠️ Advanced Features

### Customizing the Platform
- **Templates**: Edit files in `scripts/templates/` to modify document and website generation
- **Workflows**: Create custom workflow targets in the Makefile for your specific needs
- **AI Prompts**: Enhance AI analysis by modifying the prompts in the analysis scripts

### Using GitHub Actions Workflows
The repository includes several GitHub Actions for automation:

- `system-init.yml`: Complete system setup
- `job-strategy.yml`: Scheduled job search and strategy generation
- `document-generation.yml`: Create application materials
- `github-pages.yml`: Update your professional website
- `profile-update.yml`: Process updated profile documents

---

## 🎯 Command Reference

### Core Workflows
```bash
make daily-workflow              # Complete daily job search routine
make job-workflow                # Generate job strategy and documents
make full-workflow               # Full workflow with application tracking
make sync-and-publish            # Sync database and update website
```

### Individual Components 
```bash
make search-jobs                 # Only search for jobs
make generate-strategy           # Generate job search strategy
make generate-docs-for-jobs      # Create documents for high-priority jobs
make mark-applied                # Track job application status
```

### GitHub Actions
```bash
gh workflow run job-strategy.yml # Run job strategy workflow
gh workflow run gh-pages.yml     # Update GitHub Pages
```

---

## 🔧 Troubleshooting

- **Database issues**: Run `make clean` then reinitialize
- **API errors**: Verify your Gemini API key is correct
- **PDF parsing issues**: Ensure your documents use standard formatting
- **Sync problems**: Check Google Cloud credentials and permissions

---

## License

[MIT License](LICENSE)

---

## Acknowledgments
- Powered by Google Gemini API
- Uses WeasyPrint for PDF generation
- SQLAlchemy for database operations

---

*Your career deserves this level of organization. Happy job hunting!*