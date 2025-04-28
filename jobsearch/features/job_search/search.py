"""Job search functionality using core components."""
from datetime import datetime
import re
from typing import Dict, List, Optional
import json

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session, JobCache, Experience, Skill, TargetRole
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import AIEngine
from jobsearch.core.web_scraper import WebScraper
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.schemas import (
    JobSearchQuery,
    JobListing,
    SearchResult,
    CompanyOverview
)

# Initialize core components
logger = setup_logging('job_search')
storage = GCSManager()
ai_engine = AIEngine(feature_name='job_search')
web_scraper = WebScraper(rate_limit=1.0)  # Be nice to job sites
monitoring = setup_monitoring('job_search')

def normalize_linkedin_url(url: str) -> str:
    """Normalize LinkedIn job URLs to ensure consistent matching."""
    match = re.search(r'(?:jobs|view)/(\d+)', url)
    if match:
        return f"https://www.linkedin.com/jobs/view/{match.group(1)}"
    return url

def normalize_title(title: str) -> str:
    """Normalize job titles for better matching."""
    # Remove level prefixes/suffixes
    title = re.sub(r'(?i)(senior|sr\.|junior|jr\.|lead|principal|staff|associate)\s+', '', title)
    # Remove common suffixes
    title = re.sub(r'(?i)\s+(i|ii|iii|iv|v)$', '', title)
    # Convert to lowercase and strip whitespace
    return title.lower().strip()

async def generate_search_queries(company_size: Optional[str] = None) -> List[JobSearchQuery]:
    """Generate job search queries based on profile."""
    try:
        monitoring.increment('generate_queries')
        
        with get_session() as session:
            experiences = session.query(Experience).all()
            skills = session.query(Skill).all()
            target_roles = session.query(TargetRole).all()
            
            profile_data = {
                'experiences': [e.__dict__ for e in experiences],
                'skills': [s.__dict__ for s in skills],
                'target_roles': [r.__dict__ for r in target_roles]
            }
            
            if company_size:
                profile_data['company_size'] = company_size
                
        # Use AI to generate optimal search queries
        queries = await ai_engine.generate(
            prompt="Generate job search queries based on profile",
            context=profile_data,
            output_type=List[JobSearchQuery]
        )
        
        monitoring.track_success('generate_queries')
        return queries or []
        
    except Exception as e:
        monitoring.track_error('generate_queries', str(e))
        logger.error(f"Error generating search queries: {str(e)}")
        return []

async def search_jobs(queries: List[JobSearchQuery]) -> List[JobListing]:
    """Search for jobs using the provided queries."""
    try:
        monitoring.increment('search_jobs')
        results = []
        
        for query in queries:
            search_url = query.to_search_url()
            logger.info(f"Searching: {search_url}")
            
            # Use web scraper with proper rate limiting
            soup = await web_scraper.get_page(search_url)
            if not soup:
                continue
                
            # Extract job listings
            job_elements = soup.select(query.job_element_selector)
            for element in job_elements:
                try:
                    url = normalize_linkedin_url(element.select_one(query.url_selector)['href'])
                    title = element.select_one(query.title_selector).text.strip()
                    company = element.select_one(query.company_selector).text.strip()
                    location = element.select_one(query.location_selector).text.strip()
                    
                    # Get full job description
                    job_soup = await web_scraper.get_page(url)
                    if job_soup:
                        description = job_soup.select_one(query.description_selector).text.strip()
                        post_date = job_soup.select_one(query.post_date_selector)
                        post_date = post_date.text.strip() if post_date else None
                        
                        job = JobListing(
                            url=url,
                            title=title,
                            company=company,
                            location=location,
                            description=description,
                            post_date=post_date,
                            source=query.source,
                            search_query=query.query
                        )
                        results.append(job)
                        
                except Exception as e:
                    logger.warning(f"Error parsing job element: {str(e)}")
                    continue
                    
        monitoring.track_success('search_jobs')
        return results
        
    except Exception as e:
        monitoring.track_error('search_jobs', str(e))
        logger.error(f"Error searching for jobs: {str(e)}")
        return []

async def update_job_cache(jobs: List[JobListing], analyzed_jobs: Dict[str, Dict]) -> bool:
    """Update the job cache with new or updated job information."""
    try:
        monitoring.increment('update_cache')
        now = datetime.now().strftime("%Y-%m-%d")
        updated_count = 0
        new_count = 0
        
        with get_session() as session:
            for job in jobs:
                analysis = analyzed_jobs.get(job.url, {})
                company_overview = analysis.get('company_overview', CompanyOverview())
                
                # Check if job exists
                cached_job = session.query(JobCache).filter_by(url=job.url).first()
                
                if cached_job:
                    # Update existing job
                    cached_job.last_seen_date = now
                    cached_job.location = job.location
                    cached_job.post_date = job.post_date
                    cached_job.description = job.description
                    
                    # Update analysis fields
                    cached_job.match_score = analysis.get('match_score', 0)
                    cached_job.key_requirements = analysis.get('key_requirements', [])
                    cached_job.culture_indicators = analysis.get('culture_indicators', [])
                    cached_job.career_growth_potential = analysis.get('career_growth_potential', 'unknown')
                    cached_job.total_years_experience = analysis.get('total_years_experience', 0)
                    cached_job.candidate_gaps = analysis.get('candidate_gaps', [])
                    cached_job.location_type = analysis.get('location_type', 'unknown')
                    
                    # Update company overview
                    cached_job.company_size = company_overview.size
                    cached_job.company_stability = company_overview.stability
                    cached_job.glassdoor_rating = company_overview.glassdoor_rating
                    cached_job.employee_count = company_overview.employee_count
                    cached_job.industry = company_overview.industry
                    cached_job.funding_stage = company_overview.funding_stage
                    cached_job.benefits = company_overview.benefits
                    cached_job.tech_stack = company_overview.tech_stack
                    
                    updated_count += 1
                    
                else:
                    # Insert new job
                    new_job = JobCache(
                        url=job.url,
                        title=job.title,
                        company=job.company,
                        location=job.location,
                        description=job.description,
                        post_date=job.post_date,
                        first_seen_date=now,
                        last_seen_date=now,
                        search_query=job.search_query,
                        
                        # Analysis fields
                        match_score=analysis.get('match_score', 0),
                        key_requirements=analysis.get('key_requirements', []),
                        culture_indicators=analysis.get('culture_indicators', []),
                        career_growth_potential=analysis.get('career_growth_potential', 'unknown'),
                        total_years_experience=analysis.get('total_years_experience', 0),
                        candidate_gaps=analysis.get('candidate_gaps', []),
                        location_type=analysis.get('location_type', 'unknown'),
                        
                        # Company overview
                        company_size=company_overview.size,
                        company_stability=company_overview.stability,
                        glassdoor_rating=company_overview.glassdoor_rating,
                        employee_count=company_overview.employee_count,
                        industry=company_overview.industry,
                        funding_stage=company_overview.funding_stage,
                        benefits=company_overview.benefits,
                        tech_stack=company_overview.tech_stack
                    )
                    session.add(new_job)
                    new_count += 1
                    
            session.commit()
            
        logger.info(f"Updated {updated_count} jobs and added {new_count} new jobs to cache")
        monitoring.track_success('update_cache')
        return True
        
    except Exception as e:
        monitoring.track_error('update_cache', str(e))
        logger.error(f"Error updating job cache: {str(e)}")
        return False

async def main():
    """Main job search routine."""
    try:
        # Generate search queries
        queries = await generate_search_queries()
        if not queries:
            logger.error("No search queries generated")
            return False
            
        # Search for jobs
        jobs = await search_jobs(queries)
        if not jobs:
            logger.warning("No jobs found")
            return True  # Not an error, just no results
            
        # Analyze jobs
        from jobsearch.features.job_search.analysis import analyze_jobs_batch
        analyzed_jobs = await analyze_jobs_batch(jobs)
        
        # Update cache
        if not await update_job_cache(jobs, analyzed_jobs):
            logger.error("Failed to update job cache")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error in job search routine: {str(e)}")
        return False

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())