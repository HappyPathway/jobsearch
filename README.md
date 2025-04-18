# Career Automation Platform

An AI-powered job search automation system that helps you manage your professional profile, generate personalized application documents, and maintain a strategic job search.

## Overview

This platform uses AI to streamline and enhance your job search process by:

- Parsing and analyzing your resume, cover letter, and professional profile
- Generating personalized job search strategies
- Creating tailored resumes and cover letters for specific job opportunities
- Building a personal career website via GitHub Pages
- Tracking job applications and opportunities

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- GitHub account (for workflows and GitHub Pages)
- Google Gemini API key

### Setup Instructions

1. **Use this template**:
   - Click "Use this template" on GitHub to create your own repository
   - Clone your new repository locally

2. **Install dependencies**:
   ```
   make install
   ```

3. **Add your documents**:
   - Replace files in the `docs/` directory with your own:
     - `Resume.pdf`: Your current resume
     - `CoverLetter.pdf`: A general cover letter
     - `Profile.pdf`: Your LinkedIn profile export (or similar)
     - `Profile.jpeg`: Your professional headshot
     
   Note: The `profile.json` file will be automatically generated from your resume during initialization - you don't need to create it manually.

4. **Set up environment variables**:
   - Create a `.env` file in the root directory
   - Add your Gemini API key: `GEMINI_API_KEY=your_api_key_here`
   - For GitHub Actions, add this key as a repository secret

5. **Initialize the system**:
   - Option 1: Run GitHub workflow (recommended)
     ```
     gh workflow run system-init.yml
     ```
   - Option 2: Run locally
     ```
     make clean
     make init-db
     make scrape-profile
     make parse-resume
     make parse-cover-letter
     make combine-summary
     ```

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