from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date

from ..dependencies import get_db, get_current_user

# Import from installed package
from jobsearch.features.strategy_generation.generator import (
    generate_strategy,
    get_latest_strategy,
    get_strategy_by_date
)
from jobsearch.core.storage import GCSManager

router = APIRouter()

@router.post("/generate")
async def create_strategy(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    job_limit: Optional[int] = 5,
    include_recruiters: Optional[bool] = False,
    generate_docs: Optional[bool] = False
):
    """Generate a new job search strategy"""
    try:
        strategy = generate_strategy(
            job_limit=job_limit,
            include_recruiters=include_recruiters,
            generate_documents=generate_docs
        )
        
        return {
            "status": "success",
            "strategy": strategy,
            "generated_at": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate strategy: {str(e)}"
        )

@router.get("/latest")
async def get_current_strategy(
    db: Session = Depends(get_db)
):
    """Get the most recently generated strategy"""
    try:
        strategy = get_latest_strategy()
        if not strategy:
            raise HTTPException(
                status_code=404,
                detail="No strategies found"
            )
        return strategy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve strategy: {str(e)}"
        )

@router.get("/by-date/{strategy_date}")
async def get_strategy(
    strategy_date: date,
    db: Session = Depends(get_db)
):
    """Get a strategy for a specific date"""
    try:
        strategy = get_strategy_by_date(strategy_date)
        if not strategy:
            raise HTTPException(
                status_code=404,
                detail=f"No strategy found for date {strategy_date}"
            )
        return strategy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve strategy: {str(e)}"
        )