# Career Automation Platform

An AI-powered job search automation system that helps you manage your professional profile, generate personalized application documents, and maintain a strategic job search.

## Overview

This platform uses AI to streamline and enhance your job search process by:

- Parsing and analyzing your resume, cover letter, and professional profile
- Generating personalized job search strategies
- Creating tailored resumes and cover letters for specific job opportunities
- Building a personal career website via GitHub Pages
- Tracking job applications and opportunities
- Maintaining persistent data in Google Cloud Storage

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- GitHub account (for workflows and GitHub Pages)
- Google Gemini API key
- Google Cloud Project with appropriate permissions

### Setup Instructions

1. **Use this template**:
   - Click "Use this template" on GitHub to create your own repository
   - Clone your new repository locally

2. **Set up Google Cloud credentials**:
   - Ensure you have access to your organization's Google Cloud credentials
   - No manual bucket creation needed - the system will create a unique bucket automatically

3. **Install dependencies**:
   ```
   make install
   ```

4. **Add your documents**:
   - Replace files in the `docs/` directory with your own:
     - `Resume.pdf`: Your current resume
     - `CoverLetter.pdf`: A general cover letter
     - `Profile.pdf`: Your LinkedIn profile export (or similar)
     - `Profile.jpeg`: Your professional headshot
     
   Note: The `profile.json` file will be automatically generated from your resume during initialization - you don't need to create it manually.

5. **Set up environment variables and secrets**:
   - Create a `.env` file in the root directory
   - Add your Gemini API key: `GEMINI_API_KEY=your_api_key_here`
   - Ensure your GitHub organization has the following secrets:
     - `GOOGLE_CREDENTIALS`: Organization-wide Google Cloud credentials
     - `GEMINI_API_KEY`: Your Gemini API key

6. **Initialize the system**:
   ```
   gh workflow run system-init.yml
   ```
   This will:
   - Create a unique GCS bucket for your data
   - Initialize the database schema
   - Process your profile documents
   - Generate initial job search strategy
   - Set up GitHub Pages

## Features

### Profile Management

The system parses and organizes your professional information from:
- Resume (education, work history, skills)
- Cover letter (writing style, values, goals)
- LinkedIn profile (detailed work experience, skill endorsements)

All data is stored in a structured SQLite database (`career_data.db`).

### GitHub Pages Career Website

A professional portfolio website is automatically generated from your profile data:
- Professional summary
- Skills and expertise
- Work experience
- Contact information

View it at: `https://[your-username].github.io/[repo-name]/`

### Job Application Document Generation

Create tailored application materials for specific job opportunities:
- Customized resumes highlighting relevant experience
- Personalized cover letters addressing company needs
- Documents are stored in the `applications/` directory

### Job Search Strategy

Receive AI-generated job search strategies:
- Daily focus areas and priorities
- Networking suggestions
- Skill development recommendations
- Application optimization tips

## Architecture

### Data Storage

The system uses a hybrid storage approach:
- SQLite database for structured data
- Google Cloud Storage (GCS) for persistence
- Automatic database synchronization between workflows
- Versioned storage with 90-day retention policy
- Randomly generated, unique bucket names for security

### Workflows

All GitHub Actions workflows are integrated with GCS:
- `system-init.yml`: Sets up GCS infrastructure and initializes system
- `github-pages.yml`: Deploys website using latest data from GCS
- `profile-update.yml`: Updates profile data in GCS
- `job-strategy.yml`: Generates strategies using current GCS data
- `document-generation.yml`: Creates documents with latest profile data
- `integration-tests.yml`: Tests system functionality including GCS
- `strategy-cleanup.yml`: Manages old strategy files

Each workflow automatically:
- Authenticates with Google Cloud
- Syncs with the latest database state
- Persists changes back to GCS
- Creates pull requests for review when appropriate

## Usage

### Daily Workflow

1. **Generate today's strategy**:
   ```
   make generate-strategy
   ```
   This creates files in the `strategies/` directory.

2. **Generate documents for a job**:
   ```
   make generate-docs URL="job_posting_url" COMPANY="Company Name" TITLE="Job Title" DESCRIPTION="Job description text"
   ```

3. **Mark a job as applied**:
   ```
   make mark-applied URL="job_posting_url" STATUS="applied" NOTES="Any application notes"
   ```

### Using GitHub Actions

Several automated workflows are available:
- `system-init.yml`: Complete system initialization
- `github-pages.yml`: Deploy your career website
- `profile-update.yml`: Update when profile documents change
- `job-strategy.yml`: Generate job search strategies
- `document-generation.yml`: Create application documents

## Customization

### Modifying Templates

Edit files in the `scripts/templates/` directory:
- `github_pages.html`: Career website layout
- `resume.html`: Resume PDF template
- `cover_letter.html`: Cover letter PDF template

### Extending Functionality

The modular script design makes it easy to add or modify features:
- `scripts/`: Core functionality
- `models.py`: Database schema
- `utils.py`: Shared utilities

## Troubleshooting

- **Database issues**: Run `make clean` followed by reinitializing
- **API errors**: Verify your Gemini API key is correct
- **PDF parsing issues**: Ensure your documents use standard formatting

## License

[MIT License](LICENSE)

## Acknowledgments

- Powered by Google Gemini API
- Uses WeasyPrint for PDF generation
- SQLAlchemy for database operations