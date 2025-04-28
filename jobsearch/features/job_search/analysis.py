"""Job analysis and scoring functionality using core components."""
from pathlib import Path
from typing import Dict, List, Optional
import urllib.parse

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.models import Experience, Skill, TargetRole, JobCache
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import AIEngine
from jobsearch.core.web_scraper import WebScraper
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.schemas import (
    JobAnalysis, 
    GlassdoorInfo, 
    CompanyAnalysis,
    GrowthPotential,
    LocationType,
    CompanySize,
    StabilityLevel
)

# Initialize core components
logger = setup_logging('job_analyzer')
storage = GCSManager()
ai_engine = AIEngine(feature_name='job_analysis')
web_scraper = WebScraper(rate_limit=2.0)
monitoring = setup_monitoring('job_analysis')

async def analyze_job_fit(job_data: Dict, profile_data: Optional[Dict] = None) -> Optional[JobAnalysis]:
    """Analyze job posting for fit and requirements."""
    try:
        monitoring.increment('analyze_job')
        
        # Prepare job context for AI
        job_context = {
            'title': job_data.get('title', ''),
            'company': job_data.get('company', ''),
            'description': job_data.get('description', ''),
            'location': job_data.get('location', ''),
            'profile': profile_data or {}
        }
        
        # Get AI analysis
        analysis = await ai_engine.generate(
            prompt="Analyze this job posting for candidate fit and requirements",
            context=job_context,
            output_type=JobAnalysis
        )
        
        if not analysis:
            raise ValueError("Failed to generate job analysis")
            
        # Get company research from Glassdoor
        company_info = await get_glassdoor_info(job_data['company'])
        
        # Combine analysis with company research
        analysis.company_size = company_info.size if company_info else CompanySize.UNKNOWN
        analysis.company_stability = company_info.stability if company_info else StabilityLevel.UNKNOWN
        analysis.glassdoor_rating = company_info.rating if company_info else None
        analysis.employee_count = company_info.employee_count if company_info else None
        analysis.industry = company_info.industry if company_info else None
        analysis.funding_stage = company_info.funding_stage if company_info else None
        analysis.benefits = company_info.benefits if company_info else []
        analysis.tech_stack = company_info.tech_stack if company_info else []
        
        monitoring.track_success('analyze_job')
        return analysis
        
    except Exception as e:
        monitoring.track_error('analyze_job', str(e))
        logger.error(f"Error analyzing job: {str(e)}")
        return None

async def get_glassdoor_info(company_name: str) -> Optional[GlassdoorInfo]:
    """Search Glassdoor for company information."""
    try:
        monitoring.increment('glassdoor_search')
        search_url = f"https://www.glassdoor.com/Search/results.htm?keyword={urllib.parse.quote(company_name)}"
        
        # Use web scraper with proper rate limiting
        soup = await web_scraper.get_page(search_url)
        if not soup:
            return None
            
        # Analyze company page with AI
        html_content = str(soup)
        info = await ai_engine.generate(
            prompt="Extract company information from Glassdoor page",
            context={'html': html_content},
            output_type=GlassdoorInfo
        )
        
        monitoring.track_success('glassdoor_search')
        return info
        
    except Exception as e:
        monitoring.track_error('glassdoor_search', str(e))
        logger.error(f"Error getting Glassdoor info: {str(e)}")
        return None

async def analyze_jobs_batch(jobs: List[Dict]) -> List[Dict]:
    """Analyze a batch of jobs and return the analysis results."""
    try:
        monitoring.increment('analyze_batch')
        results = []
        
        # Get profile data once for the batch
        with get_session() as session:
            experiences = session.query(Experience).all()
            skills = session.query(Skill).all()
            target_roles = session.query(TargetRole).all()
            
            profile_data = {
                'experiences': [e.__dict__ for e in experiences],
                'skills': [s.__dict__ for s in skills],
                'target_roles': [r.__dict__ for r in target_roles]
            }
        
        # Process jobs in parallel batches of 5
        from asyncio import gather, Semaphore
        sem = Semaphore(5)
        
        async def process_job(job):
            async with sem:
                return await analyze_job_fit(job, profile_data)
                
        analysis_tasks = [process_job(job) for job in jobs]
        analyses = await gather(*analysis_tasks)
        
        # Combine job data with analysis
        for job, analysis in zip(jobs, analyses):
            if analysis:
                result = {
                    'url': job['url'],
                    'title': job['title'],
                    'company': job['company'],
                    'analysis': analysis.dict()
                }
                results.append(result)
                
        monitoring.track_success('analyze_batch')
        return results
        
    except Exception as e:
        monitoring.track_error('analyze_batch', str(e))
        logger.error(f"Error analyzing job batch: {str(e)}")
        return []

async def update_job_analysis(job_url: str) -> bool:
    """Update analysis for a specific job."""
    try:
        monitoring.increment('update_analysis')
        
        with get_session() as session:
            job = session.query(JobCache).filter_by(url=job_url).first()
            if not job:
                logger.error(f"Job not found: {job_url}")
                return False
                
            # Get fresh analysis
            job_data = {
                'url': job.url,
                'title': job.title,
                'company': job.company,
                'description': job.description,
                'location': job.location
            }
            
            analysis = await analyze_job_fit(job_data)
            if not analysis:
                logger.error(f"Failed to analyze job: {job_url}")
                return False
                
            # Update job record
            job.match_score = analysis.match_score
            job.key_requirements = analysis.key_requirements
            job.culture_indicators = analysis.culture_indicators
            job.career_growth_potential = analysis.career_growth_potential
            job.total_years_experience = analysis.total_years_experience
            job.candidate_gaps = analysis.candidate_gaps
            job.location_type = analysis.location_type
            job.company_size = analysis.company_size
            job.company_stability = analysis.company_stability
            job.glassdoor_rating = analysis.glassdoor_rating
            job.employee_count = analysis.employee_count
            job.industry = analysis.industry
            job.funding_stage = analysis.funding_stage
            job.benefits = analysis.benefits
            job.tech_stack = analysis.tech_stack
            
            session.commit()
            
        monitoring.track_success('update_analysis')
        return True
        
    except Exception as e:
        monitoring.track_error('update_analysis', str(e))
        logger.error(f"Error updating job analysis: {str(e)}")
        return False