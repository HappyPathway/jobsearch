"""Job search functionality using Pydantic-AI."""
import os
from typing import List, Optional, Dict
import asyncio
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from pydantic_ai import Agent
from dotenv import load_dotenv

from jobsearch.core.logging_utils import setup_logging
from jobsearch.core.schemas import (
    JobListing, JobAnalysis, JobSearchResult,
    LocationType, CompanySize, GrowthPotential, StabilityLevel
)
from jobsearch.core.models import JobCache, JobApplication
from jobsearch.core.database import get_engine, get_session
from sqlalchemy.orm import Session

logger = setup_logging('job_search')

# Load environment variables
load_dotenv()

class JobSearchAgent:
    """Agent for searching and analyzing jobs."""
    
    def __init__(self, monitoring=None):
        """Initialize job search agent with Gemini model and monitoring."""
        from jobsearch.features.job_search.monitoring import setup_job_search_monitoring
        
        # Set up monitoring if not provided
        self.monitoring = monitoring or setup_job_search_monitoring(
            environment=os.getenv("ENVIRONMENT", "development")
        )
        
        # Initialize search agent with monitoring
        self.search_agent = Agent(
            'google-gla:gemini-1.5-pro',
            output_type=List[JobListing],
            system_prompt="""You are an expert job search assistant. 
            Extract detailed job listings from search results, ensuring all fields are properly populated.
            Pay special attention to separating location and job description.""",
            monitoring=self.monitoring.monitoring,
            instrumentation={
                'track_tokens': True,
                'track_latency': True,
                'track_errors': True,
                'track_retries': True
            }
        )
        
        # Initialize analysis agent with monitoring
        self.analysis_agent = Agent(
            'google-gla:gemini-1.5-pro',
            output_type=JobAnalysis,
            system_prompt="""You are an expert job analyst.
            Analyze job postings thoroughly, considering both explicit requirements and implicit indicators.
            Be data-driven in your analysis and provide clear reasoning for your assessments.""",
            monitoring=self.monitoring.monitoring,
            instrumentation={
                'track_tokens': True,
                'track_latency': True,
                'track_errors': True,
                'track_retries': True,
                'track_success_rate': True
            }
        )
        
    async def search_linkedin_jobs(
        self,
        query: str,
        location: str = "United States",
        limit: int = 5
    ) -> List[JobSearchResult]:
        """Search LinkedIn for jobs and analyze matches."""
        logger.info(f"Searching LinkedIn jobs for query: {query}")
        
        # First check cache
        cached_jobs = self._get_cached_jobs(query)
        if len(cached_jobs) >= limit:
            return cached_jobs[:limit]
            
        # If not enough cached results, search LinkedIn
        base_url = "https://www.linkedin.com/jobs/search"
        params = {
            "keywords": query,
            "location": location,
            "geoId": "103644278",  # United States
            "f_WT": "2",  # Remote jobs
            "pageSize": str(limit * 2),  # Request more to account for duplicates
            "sortBy": "R"  # Sort by relevance
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        try:
            # Get search results
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            
            # Extract job listings using the search agent
            job_listings = await self.search_agent.run(
                f"Extract job listings from this LinkedIn search results page. HTML content:\n{response.text}"
            )
            
            # Analyze each job
            results = []
            for job in job_listings:
                analysis = await self._analyze_job(job)
                results.append(JobSearchResult(
                    listing=job,
                    analysis=analysis,
                    search_query=query
                ))
                
            # Cache the results
            await self._cache_results(results)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching LinkedIn: {str(e)}")
            return cached_jobs[:limit]
    
    async def _analyze_job(self, job: JobListing) -> Optional[JobAnalysis]:
        """Analyze a job listing using the analysis agent."""
        try:
            # Get detailed job info if needed
            # For now, we'll just use what we have
            job_details = f"""
            Title: {job.title}
            Company: {job.company}
            Location: {job.location}
            Description: {job.description}
            """
            
            # Run analysis
            analysis = await self.analysis_agent.run(
                f"Analyze this job posting thoroughly:\n{job_details}",
                temperature=0.2  # Lower temperature for more consistent analysis
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing job {job.title}: {str(e)}")
            return None
    
    def _get_cached_jobs(self, query: str) -> List[JobSearchResult]:
        """Get cached job results from database."""
        try:
            with get_session() as session:
                cached = session.query(JobCache).filter(
                    JobCache.search_query == query
                ).all()
                
                return [
                    JobSearchResult(
                        listing=JobListing(
                            url=job.url,
                            title=job.title,
                            company=job.company,
                            location=job.location,
                            description=job.description,
                            post_date=job.post_date,
                            first_seen_date=datetime.fromisoformat(job.first_seen_date),
                            last_seen_date=datetime.fromisoformat(job.last_seen_date)
                        ),
                        analysis=JobAnalysis(
                            match_score=job.match_score,
                            key_requirements=job.key_requirements,
                            culture_indicators=job.culture_indicators,
                            career_growth_potential=job.career_growth_potential,
                            total_years_experience=job.total_years_experience,
                            candidate_gaps=job.candidate_gaps,
                            location_type=job.location_type,
                            application_priority=job.application_priority,
                            company_overview=job.company_overview,
                            reasoning=job.reasoning
                        ) if job.match_score else None,
                        search_query=query
                    )
                    for job in cached
                ]
        except Exception as e:
            logger.error(f"Error getting cached jobs: {str(e)}")
            return []
    
    async def _cache_results(self, results: List[JobSearchResult]):
        """Cache job results in database."""
        try:
            with get_session() as session:
                for result in results:
                    # Check if job already exists
                    existing = session.query(JobCache).filter(
                        JobCache.url == result.listing.url
                    ).first()
                    
                    if existing:
                        # Update last seen date and any new analysis
                        existing.last_seen_date = datetime.now().isoformat()
                        if result.analysis:
                            existing.match_score = result.analysis.match_score
                            existing.key_requirements = result.analysis.key_requirements
                            existing.culture_indicators = result.analysis.culture_indicators
                            existing.career_growth_potential = result.analysis.career_growth_potential
                            existing.total_years_experience = result.analysis.total_years_experience
                            existing.candidate_gaps = result.analysis.candidate_gaps
                            existing.location_type = result.analysis.location_type
                            existing.application_priority = result.analysis.application_priority
                            existing.company_overview = result.analysis.company_overview.dict()
                            existing.reasoning = result.analysis.reasoning
                    else:
                        # Create new cache entry
                        cache_entry = JobCache(
                            url=result.listing.url,
                            title=result.listing.title,
                            company=result.listing.company,
                            location=result.listing.location,
                            description=result.listing.description,
                            post_date=result.listing.post_date,
                            first_seen_date=datetime.now().isoformat(),
                            last_seen_date=datetime.now().isoformat(),
                            search_query=result.search_query
                        )
                        
                        if result.analysis:
                            cache_entry.match_score = result.analysis.match_score
                            cache_entry.key_requirements = result.analysis.key_requirements
                            cache_entry.culture_indicators = result.analysis.culture_indicators
                            cache_entry.career_growth_potential = result.analysis.career_growth_potential
                            cache_entry.total_years_experience = result.analysis.total_years_experience
                            cache_entry.candidate_gaps = result.analysis.candidate_gaps
                            cache_entry.location_type = result.analysis.location_type
                            cache_entry.application_priority = result.analysis.application_priority
                            cache_entry.company_overview = result.analysis.company_overview.dict()
                            cache_entry.reasoning = result.analysis.reasoning
                            
                        session.add(cache_entry)
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Error caching results: {str(e)}")


# Create singleton instance
job_search_agent = JobSearchAgent()
