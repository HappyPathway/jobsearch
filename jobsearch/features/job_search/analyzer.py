#!/usr/bin/env python3
"""Command-line tool for analyzing job postings."""
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
import asyncio

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.models import JobCache, JobApplication
from jobsearch.core.storage import GCSManager 
from jobsearch.core.ai import AIEngine
from jobsearch.core.web_scraper import WebScraper
from jobsearch.core.schemas import JobAnalysis, JobInfo

# Initialize core components
logger = setup_logging('job_analyzer')
storage = GCSManager()
ai_engine = AIEngine(feature_name='job_analysis')
web_scraper = WebScraper(rate_limit=2.0)

async def analyze_jobs(jobs_to_analyze: List[JobInfo]) -> Dict[str, JobAnalysis]:
    """Analyze a batch of jobs.
    
    Args:
        jobs_to_analyze: List of job info objects
        
    Returns:
        Dict mapping job URLs to analysis results
    """
    try:
        results = {}
        for job in jobs_to_analyze:
            result = await analyze_job(job)
            if result:
                results[job.url] = result
                
                # Update database
                with get_session() as session:
                    cached_job = session.query(JobCache).filter_by(url=job.url).first()
                    if cached_job:
                        cached_job.match_score = result.match_score
                        cached_job.application_priority = result.priority
                        cached_job.key_requirements = json.dumps(result.requirements)
                        cached_job.culture_indicators = json.dumps(result.culture)
                        cached_job.career_growth_potential = result.growth_potential
                        session.commit()
                        
                logger.info(f"Analyzed job: {job.title} at {job.company}")
                
        storage.sync_db()
        return results
        
    except Exception as e:
        logger.error(f"Error analyzing jobs: {str(e)}")
        return {}

async def analyze_job(job: JobInfo) -> Optional[JobAnalysis]:
    """Analyze a single job posting.
    
    Args:
        job: Job info object
        
    Returns:
        Analysis result or None on failure
    """
    try:
        result = await ai_engine.analyze_job(
            title=job.title,
            company=job.company,
            description=job.description,
            url=job.url,
            output_type=JobAnalysis
        )
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing job {job.title}: {str(e)}")
        return None

async def main() -> int:
    """Main CLI entrypoint.
    
    Returns:
        0 on success, 1 on failure
    """
    try:
        if len(sys.argv) < 2:
            logger.error("Usage: analyze_jobs.py <jobs_file.json>")
            return 1
            
        jobs_file = Path(sys.argv[1])
        if not jobs_file.exists():
            logger.error(f"Jobs file not found: {jobs_file}")
            return 1
            
        with open(jobs_file) as f:
            jobs_data = json.load(f)
            
        jobs = [
            JobInfo(
                url=job['url'],
                title=job['title'],
                company=job['company'],
                description=job['description']
            )
            for job in jobs_data
        ]
        
        results = await analyze_jobs(jobs)
        if not results:
            logger.error("No jobs were successfully analyzed")
            return 1
            
        logger.info(f"Successfully analyzed {len(results)} jobs")
        return 0
        
    except Exception as e:
        logger.error(f"Error analyzing jobs: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main()))