"""Job search interface using Pydantic-AI implementation."""
from typing import List, Optional
from jobsearch.core.schemas import JobSearchResult
from jobsearch.features.job_search.pydantic_search import job_search_agent


async def search_jobs(
    query: str,
    location: Optional[str] = None,
    limit: int = 5
) -> List[JobSearchResult]:
    """
    Search for jobs using the Pydantic-AI implementation.
    
    Args:
        query: Search query string
        location: Optional location filter
        limit: Maximum number of results to return
        
    Returns:
        List[JobSearchResult]: List of job search results with analysis
    """
    return await job_search_agent.search_linkedin_jobs(
        query=query,
        location=location or "United States",
        limit=limit
    )
