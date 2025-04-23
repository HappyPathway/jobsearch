# Job Search API Service

REST API service for the Job Search Automation Platform that provides endpoints for job search, document generation, profile management, and career strategy planning.

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Google Cloud credentials
- Gemini API key
- Slack workspace (optional)
- Medium API key (optional)

## Installation

1. Clone the repository (if you haven't already):
   ```bash
   git clone <repository-url>
   cd jobsearch/app
   ```

2. Copy the environment file and configure your credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials and configuration
   ```

3. Install dependencies and initialize:
   ```bash
   make install
   make init
   ```

## Running the Service

### Local Development

1. Install the jobsearch package and API service in development mode:
   ```bash
   make install
   ```

2. Initialize the environment:
   ```bash
   make init
   ```

3. Run the service:
   ```bash
   make run
   ```

### Docker Deployment

1. Build the Docker image:
   ```bash
   make build
   ```

2. Start the service:
   ```bash
   make run
   ```

3. Stop the service:
   ```bash
   make stop
   ```

## API Endpoints

### Jobs

- `GET /api/jobs/search` - Search for jobs with filters
- `GET /api/jobs/{job_id}` - Get job details
- `POST /api/jobs/{job_id}/apply` - Mark job as applied
- `GET /api/jobs/applications` - List job applications

### Profile

- `GET /api/profile/summary` - Get profile summary
- `POST /api/profile/skills` - Add new skill
- `GET /api/profile/skills` - List all skills
- `POST /api/profile/experiences` - Add new experience
- `GET /api/profile/experiences` - List all experiences
- `POST /api/profile/upload/resume` - Upload and parse resume

### Documents

- `POST /api/documents/generate` - Generate resume and cover letter
- `GET /api/documents/{document_id}` - Get document details
- `GET /api/documents` - List all documents

### Strategies

- `POST /api/strategies/generate` - Generate job search strategy
- `GET /api/strategies/latest` - Get current strategy
- `GET /api/strategies/by-date/{date}` - Get strategy by date

### Web Presence

- `POST /api/web-presence/github-pages/generate` - Generate GitHub Pages
- `POST /api/web-presence/medium/article` - Generate/publish Medium article

## Development

### Running Tests

```bash
make test
```

### Code Quality

```bash
make lint
```

### Cleaning Up

```bash
make clean
```

## Configuration

All configuration is done through environment variables. See `.env.example` for available options.

## Architecture

The API service is built with FastAPI and uses the jobsearch package for core functionality:

```
app/
├── main.py              # FastAPI application
├── dependencies.py      # Shared dependencies
├── routers/            # API route handlers
├── models/             # Pydantic models
├── scripts/            # Utility scripts
└── tests/              # Test suite
```

## Security

- Use proper credentials management in production
- Restrict CORS origins
- Enable authentication for all endpoints
- Use HTTPS in production
- Keep dependencies updated

## Monitoring

The service provides:
- Health check endpoint at `/`
- Docker health checks
- Detailed logging
- Error tracking

## Troubleshooting

1. **Database Issues**
   - Run `make init` to reinitialize database
   - Check GCS connection

2. **Credential Issues**
   - Verify `.env` configuration
   - Check credential file paths

3. **Docker Issues**
   - Run `make clean` then rebuild
   - Check Docker logs