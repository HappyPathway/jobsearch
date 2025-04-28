# Database Architecture

## Current Schema

### Core Tables

1. **Experiences**
```sql
CREATE TABLE experiences (
    id INTEGER PRIMARY KEY,
    company TEXT,
    title TEXT,
    start_date TEXT,
    end_date TEXT,
    description TEXT
);
```

2. **Skills**
```sql
CREATE TABLE skills (
    id INTEGER PRIMARY KEY,
    skill_name TEXT UNIQUE
);
```

3. **Experience Skills (Junction)**
```sql
CREATE TABLE experience_skills (
    experience_id INTEGER,
    skill_id INTEGER,
    FOREIGN KEY (experience_id) REFERENCES experiences(id),
    FOREIGN KEY (skill_id) REFERENCES skills(id)
);
```

4. **Target Roles**
```sql
CREATE TABLE target_roles (
    id INTEGER PRIMARY KEY,
    role_name TEXT UNIQUE,
    priority INTEGER,
    match_score FLOAT,
    reasoning TEXT,
    source TEXT,
    last_updated TEXT,
    requirements TEXT,  -- JSON array
    next_steps TEXT    -- JSON array
);
```

### Document Tables

1. **Resume Sections**
```sql
CREATE TABLE resume_sections (
    id INTEGER PRIMARY KEY,
    section_name TEXT,
    content TEXT
);
```

2. **Cover Letter Sections**
```sql
CREATE TABLE cover_letter_sections (
    id INTEGER PRIMARY KEY,
    section_name TEXT,
    content TEXT
);
```

### Job Management

1. **Job Cache**
```sql
CREATE TABLE job_cache (
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE,
    title TEXT,
    company TEXT,
    description TEXT,
    location TEXT,
    post_date TEXT,
    first_seen_date TEXT,
    last_seen_date TEXT,
    match_score FLOAT,
    priority TEXT,
    requirements TEXT,  -- JSON array
    analysis TEXT      -- JSON object
);
```

2. **Job Applications**
```sql
CREATE TABLE job_applications (
    id INTEGER PRIMARY KEY,
    job_cache_id INTEGER,
    application_date TEXT,
    status TEXT,
    resume_path TEXT,
    cover_letter_path TEXT,
    notes TEXT,
    FOREIGN KEY (job_cache_id) REFERENCES job_cache(id)
);
```

## Data Flow

1. **Profile Data Flow**
   - LinkedIn PDF -> Profile Parser -> Experiences/Skills Tables
   - Resume PDF -> Resume Parser -> Resume Sections Table
   - Cover Letter PDF -> Cover Letter Parser -> Cover Letter Sections Table

2. **Job Data Flow**
   - Job Sources -> Job Search -> Job Cache Table
   - Job Analysis -> Job Cache Updates
   - Applications -> Job Applications Table

3. **Document Generation Flow**
   - Profile Data + Job Data -> Document Generator
   - Generated Documents -> Google Cloud Storage
   - Application Records -> Job Applications Table

## Sync Mechanism

1. **Local Operations**
   - SQLite for local CRUD operations
   - File-based transactions
   - Immediate consistency

2. **Cloud Sync**
   - Periodic uploads to GCS
   - Download on startup
   - Conflict resolution (latest wins)

## Known Limitations

1. **Concurrency**
   - Single writer at a time
   - No distributed transactions
   - File-level locking

2. **Scaling**
   - Limited by file size
   - No horizontal scaling
   - Sync overhead increases with size

## Monitoring

1. **Health Metrics**
   - Database size
   - Sync frequency
   - Error rates

2. **Performance Metrics**
   - Query times
   - Sync duration
   - Cache hit rates
