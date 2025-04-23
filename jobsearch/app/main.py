"""Main FastAPI application module."""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
import os
from pathlib import Path
from dotenv import load_dotenv

# Import from installed jobsearch package
from jobsearch.core.storage import GCSManager
from jobsearch.core.database import init_database
from jobsearch.core.logging import setup_logging

# Import routers
from .routers import jobs, profile, documents, strategies, web_presence
from .dependencies import get_current_user

# Load environment variables
load_dotenv()

# Initialize logging
logger = setup_logging('api')

# Initialize the FastAPI application
app = FastAPI(
    title="Job Search Automation Platform API",
    description="""
    REST API for the Job Search Automation Platform that provides endpoints for:
    
    * Job search and application tracking
    * Professional profile management
    * Document generation (resumes and cover letters)
    * Career strategy planning
    * Web presence management (GitHub Pages and Medium)
    
    ## Features
    
    * **Automated Job Search**: Search and track job applications
    * **Smart Document Generation**: AI-powered resume and cover letter generation
    * **Profile Management**: Manage skills, experience, and career objectives
    * **Strategy Planning**: Get personalized job search strategies
    * **Web Presence**: Manage professional online presence
    
    ## Authentication
    
    Most endpoints require authentication using JWT tokens. Include the token in
    the Authorization header:
    ```
    Authorization: Bearer <your_token>
    ```
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "url": "https://github.com/yourusername/jobsearch",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with tags for API documentation
app.include_router(
    jobs.router,
    prefix="/api/jobs",
    tags=["jobs"],
    dependencies=[Depends(get_current_user)]
)
app.include_router(
    profile.router,
    prefix="/api/profile",
    tags=["profile"],
    dependencies=[Depends(get_current_user)]
)
app.include_router(
    documents.router,
    prefix="/api/documents",
    tags=["documents"],
    dependencies=[Depends(get_current_user)]
)
app.include_router(
    strategies.router,
    prefix="/api/strategies",
    tags=["strategies"],
    dependencies=[Depends(get_current_user)]
)
app.include_router(
    web_presence.router,
    prefix="/api/web-presence",
    tags=["web-presence"],
    dependencies=[Depends(get_current_user)]
)

def custom_openapi():
    """Generate custom OpenAPI schema with additional metadata."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    
    # Apply security globally
    openapi_schema["security"] = [{"bearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.on_event("startup")
async def startup_event():
    """Initialize database and storage on startup."""
    try:
        # Initialize database using jobsearch package
        init_database()
        logger.info("Database initialized successfully")
        
        # Initialize GCS connection
        storage = GCSManager()
        # Verify GCS connection by syncing database
        storage.sync_db()
        logger.info("GCS connection verified successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Job Search Automation Platform API",
        "version": "1.0.0"
    }