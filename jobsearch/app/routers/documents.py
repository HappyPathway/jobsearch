from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List
from sqlalchemy.orm import Session
from datetime import datetime

from ..models.documents import (
    DocumentCreate, DocumentResponse, GenerateRequest, 
    GenerateResponse, GenerationOptions
)
from ..dependencies import get_db, get_current_user, storage

# Import from installed package
from jobsearch.features.document_generation.generator import generate_job_documents
from jobsearch.core.models import JobCache, Document
from jobsearch.core.storage import GCSManager

router = APIRouter()

@router.post("/generate", response_model=GenerateResponse)
async def generate_documents(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate tailored resume and cover letter for a job"""
    # Get job details
    job = db.query(JobCache).filter(JobCache.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Generate documents using the jobsearch package
        resume_path, cover_letter_path = generate_job_documents(
            job_info=job.to_dict(),
            use_writing_pass=request.options.writing_enhancement,
            use_visual_resume=request.options.use_visual_resume,
            include_projects=request.options.include_projects,
            template_name=request.options.template_name
        )
        
        # Create document records
        resume_doc = Document(
            title=f"Resume - {job.company}",
            doc_type="resume",
            job_id=job.id,
            gcs_path=resume_path,
            created_at=datetime.utcnow()
        )
        cover_doc = Document(
            title=f"Cover Letter - {job.company}",
            doc_type="cover_letter",
            job_id=job.id,
            gcs_path=cover_letter_path,
            created_at=datetime.utcnow()
        )
        
        db.add(resume_doc)
        db.add(cover_doc)
        db.commit()
        
        # Generate download URLs
        storage = GCSManager()
        resume_url = storage.get_download_url(resume_path)
        cover_letter_url = storage.get_download_url(cover_letter_path)
        
        return GenerateResponse(
            resume_id=resume_doc.id,
            cover_letter_id=cover_doc.id,
            resume_url=resume_url,
            cover_letter_url=cover_letter_url,
            generation_time=datetime.utcnow(),
            status="completed"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Document generation failed: {str(e)}"
        )

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get document details by ID"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Generate download URL
    storage = GCSManager()
    document.download_url = storage.get_download_url(document.gcs_path)
    
    return document

@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    job_id: int = None,
    doc_type: str = None,
    db: Session = Depends(get_db)
):
    """List documents with optional filters"""
    query = db.query(Document)
    
    if job_id:
        query = query.filter(Document.job_id == job_id)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
        
    documents = query.order_by(Document.created_at.desc()).all()
    
    # Generate download URLs
    storage = GCSManager()
    for doc in documents:
        doc.download_url = storage.get_download_url(doc.gcs_path)
    
    return documents