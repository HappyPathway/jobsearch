# Storage Module

The Storage module provides Google Cloud Storage (GCS) management utilities for the JobSearch application. It centralizes all cloud storage operations, handling file uploads, downloads, and database synchronization.

## GCSManager Class

The core component of the module is the `GCSManager` class, which manages all interactions with Google Cloud Storage.

### Key Features

- **Database Synchronization**: Handles uploading and downloading the SQLite database to/from GCS
- **Locking Mechanism**: Prevents conflicts with a robust lock system for database operations
- **File Management**: Provides methods for general file operations (upload, download, list, delete)
- **Error Handling**: Includes retry logic and safe operations with proper error logging
- **Application-Specific Operations**: Specialized methods for job applications and strategy files

### Database Operations

#### download_db()
Downloads the database file from GCS to the local system.

#### upload_db()
Uploads the local database file to GCS.

#### sync_db()
Synchronizes the local database with GCS without lock management.

#### sync_and_upload_db()
Downloads the latest database, then uploads the local changes with proper lock handling.

### Locking System

The module implements a robust locking system to prevent concurrent database access:

#### acquire_lock()
Attempts to acquire a lock for database operations with:
- Lock file creation in GCS
- Stale lock detection (locks older than 5 minutes)
- Retry mechanism with configurable attempts and delays

#### release_lock()
Releases the database lock by deleting the lock file in GCS.

#### force_unlock()
Forces removal of a lock, intended for administrative use.

### File Operations

#### upload_file(local_path, gcs_path)
Uploads a local file to GCS at the specified path.

#### download_file(gcs_path, local_path)
Downloads a file from GCS to the specified local path.

#### list_files(prefix=None)
Returns a list of files in the GCS bucket, optionally filtered by prefix.

#### file_exists(gcs_path)
Checks if a file exists at the specified GCS path.

#### delete_file(gcs_path)
Deletes a file from GCS.

### Application-Specific Methods

#### read_application_files(application_date, company, role)
Reads application files (resume, cover letter) for a specific job application.

#### read_strategy(strategy_date)
Reads a job search strategy file from a specific date.

### Safety Utilities

#### safe_upload(content, gcs_path)
Safely uploads content to GCS with retry logic.

#### safe_download(gcs_path)
Safely downloads content from GCS with retry logic.

## Global Instance

The module creates a global `gcs` instance that's used throughout the application:

```python
# Global instance
gcs = GCSManager()
```

## Usage Example

```python
from jobsearch.core.storage import gcs

# Database operations
gcs.sync_db()  # Download latest database

# File operations
resume_path = "resumes/my_resume_2023.pdf"
if gcs.file_exists(resume_path):
    # Download the file
    gcs.download_file(resume_path, "./local_resume.pdf")

# Upload a new file
gcs.upload_file("./updated_resume.pdf", "resumes/my_resume_2023.pdf")

# List files in a directory
strategy_files = gcs.list_files(prefix="strategies/")
print(f"Found {len(strategy_files)} strategy files")

# Read application files
files = gcs.read_application_files(
    application_date="2023-04-15", 
    company="TechCorp", 
    role="Cloud Architect"
)
```

## Configuration

The GCSManager reads its configuration from a JSON file:
- Path: `/config/gcs.json`
- Required field: `GCS_BUCKET_NAME`

## Integration with Other Modules

The Storage module is used extensively by:
- **Database Module**: For synchronizing database changes
- **Job Search Module**: For storing job search strategies and application documents
- **Document Generation Module**: For storing generated resumes and cover letters