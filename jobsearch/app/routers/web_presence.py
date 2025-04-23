from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
from sqlalchemy.orm import Session

from ..dependencies import get_db, get_current_user

# Import from installed package
from jobsearch.features.web_presence.github_pages import generate_pages
from jobsearch.features.web_presence.medium import generate_article
from jobsearch.core.storage import GCSManager

router = APIRouter()

@router.post("/github-pages/generate")
async def rebuild_github_pages(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger a rebuild of GitHub Pages portfolio"""
    try:
        background_tasks.add_task(generate_pages)
        return {
            "status": "started",
            "message": "GitHub Pages generation started in background"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start GitHub Pages generation: {str(e)}"
        )

@router.post("/medium/article")
async def create_medium_article(
    job_ids: List[int],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    preview_only: Optional[bool] = True
):
    """Generate and optionally publish a Medium article about selected jobs"""
    try:
        article_text = generate_article(job_ids, preview=preview_only)
        
        if preview_only:
            return {
                "status": "preview",
                "content": article_text
            }
        else:
            background_tasks.add_task(
                generate_article, 
                job_ids, 
                preview=False
            )
            return {
                "status": "publishing",
                "message": "Article generation and publishing started"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Medium article: {str(e)}"
        )