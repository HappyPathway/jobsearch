# Database Module

The Database module provides SQLAlchemy database models and configuration for the JobSearch application. It defines the core schema for storing job search-related data and handles database sessions with GCS synchronization.

## Database Models

### Experience
Stores professional experience information:
- Company name
- Job title
- Start and end dates
- Description
- Many-to-many relationship with Skills

### Skill
Represents professional skills:
- Skill name
- Many-to-many relationship with Experiences

### TargetRole
Defines target job roles for career planning:
- Role name
- Priority level
- Match score
- Requirements (stored as JSON)
- Next steps (stored as JSON)

### JobCache
Stores job listings with detailed information:
- URL, title, company, description
- Location and post date
- First and last seen dates
- Match score and application priority
- Key requirements (JSON array)
- Culture indicators (JSON array)
- Company information (size, stability, Glassdoor rating)

### JobApplication
Tracks job applications:
- Relationship to JobCache
- Application date
- Status
- Paths to resume and cover letter
- Notes

### RecruiterContact
Stores information about recruiters:
- Name, title, company
- URL (LinkedIn profile)
- Contact status and dates
- Notes

### Resume and Cover Letter Models
Additional models for storing resume and cover letter sections.

## Database Operations

### get_engine()
Returns SQLAlchemy engine with latest database from GCS. This function:
- Locates the SQLite database file
- Creates an engine connection
- Ensures the latest version is synced from GCS
- Returns the configured engine

### get_session()
Context manager for database sessions that handles:
- GCS locking to prevent concurrent access
- Session creation
- Automatic commits
- Database upload to GCS after changes
- Error handling with rollback
- Proper session cleanup

## Usage Example

```python
from jobsearch.core.database import get_session, JobCache, Skill

# Using the session context manager
with get_session() as session:
    # Query example
    high_priority_jobs = session.query(JobCache).filter(
        JobCache.application_priority == 'high'
    ).all()
    
    # Create example
    new_skill = Skill(skill_name="Terraform")
    session.add(new_skill)
    
    # Changes are automatically committed and
    # uploaded to GCS when the context manager exits
```

## Integration with Storage

This module integrates closely with the Storage module to:
- Download the latest database from GCS before operations
- Upload changes to GCS after commits
- Implement a locking mechanism to prevent conflicts

## Important Notes

- All database operations should use the `get_session()` context manager to ensure proper GCS synchronization
- The database is automatically created if it doesn't exist
- Tables are created on first run with `create_tables_if_missing()`
- JSON data is stored as text and needs to be parsed in application code