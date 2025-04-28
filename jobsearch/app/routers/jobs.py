from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Union, Optional, Dict
from sqlalchemy.orm import Session
from datetime import datetime

from ..models.jobs import JobResponse, JobApplicationStatus
from ..dependencies import get_db

# Import core functionality from installed package
from jobsearch.core.models import JobCache, JobApplication
from jobsearch.features.job_search.search import search_jobs as job_search_service
from jobsearch.features.job_search.analysis import analyze_job_fit

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

@router.get("/search", response_model=List[JobResponse])
async def search_jobs(
    keywords: str = Query(..., description="Search keywords"),
    location: Optional[str] = Query(None, description="Job location"),
    remote_only: bool = Query(False, description="Filter for remote jobs only"),
    min_match_score: float = Query(0.0, description="Minimum match score"),
    limit: int = Query(10, description="Maximum number of results"),
    db: Session = Depends(get_db)
):
    """Search for jobs based on given parameters"""
    try:
        jobs = job_search_service(
            keywords=keywords,
            location=location,
            remote_only=remote_only,
            min_match_score=min_match_score,
            limit=limit
        )
        return jobs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search jobs: {str(e)}"
        )

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get details for a specific job"""
    job = db.query(JobCache).filter(JobCache.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )
    
    try:
        # Analyze job fit using the service
        job_analysis = analyze_job_fit(job)
        job.match_score = job_analysis.get('match_score', 0.0)
        job.career_growth_potential = job_analysis.get('growth_potential')
        return job
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze job: {str(e)}"
        )

@router.post("/{job_id}/apply", response_model=JobApplicationStatus)
async def mark_job_applied(
    job_id: int,
    application_status: JobApplicationStatus,
    db: Session = Depends(get_db)
):
    """Mark a job as applied and store application details"""
    job = db.query(JobCache).filter(JobCache.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )
        
    try:
        # Check if application already exists
        existing_application = db.query(JobApplication).filter(
            JobApplication.job_cache_id == job_id
        ).first()
        
        if existing_application:
            # Update existing application
            existing_application.status = application_status.status
            if application_status.notes:
                existing_application.notes = (existing_application.notes or "") + f"\n[{datetime.now().isoformat()}] {application_status.notes}"
            if application_status.resume_path:
                existing_application.resume_path = application_status.resume_path
            if application_status.cover_letter_path:
                existing_application.cover_letter_path = application_status.cover_letter_path
            application = existing_application
        else:
            # Create new application
            application = JobApplication(
                job_cache_id=job_id,
                application_date=datetime.now().isoformat(),
                status=application_status.status,
                notes=application_status.notes,
                resume_path=application_status.resume_path,
                cover_letter_path=application_status.cover_letter_path
            )
            db.add(application)
        
        db.commit()
        db.refresh(application)
        return application
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save application: {str(e)}"
        )

@router.get("/applications", response_model=List[JobApplicationStatus])
async def get_applications(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of job applications with optional status filter"""
    try:
        query = db.query(JobApplication).join(JobCache)
        if status:
            query = query.filter(JobApplication.status == status)
        return query.order_by(JobApplication.application_date.desc()).all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve applications: {str(e)}"
        )