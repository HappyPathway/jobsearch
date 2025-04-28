"""Job analysis and scoring functionality."""
from typing import Dict, List, Optional
from pathlib import Path

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.storage import GCSManager
from jobsearch.core.models import JobCache, Experience, Skill
from jobsearch.core.ai import AIEngine
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.web_scraper import WebScraper
from jobsearch.core.schemas import (
    JobAnalysis,
    GlassdoorInfo,
    CompanyAnalysis,
    LocationType,
    CompanySize, 
    StabilityLevel
)

# Initialize core components
logger = setup_logging('job_analysis')
storage = GCSManager()
ai_engine = AIEngine(feature_name='job_analysis')
web_scraper = WebScraper(rate_limit=2.0)
monitoring = setup_monitoring('job_analysis')

async def analyze_job_with_gemini(job_info: Dict) -> Optional[JobAnalysis]:
    """Use AI to analyze job posting and provide insights."""
    try:
        monitoring.increment('job_analysis')
        logger.info(f"Analyzing job: {job_info.get('title')} at {job_info.get('company')}")
        
        # Get profile data for context
        with get_session() as session:
            experiences = session.query(Experience).all()
            skills = session.query(Skill).all()
            
            exp_data = []
            for exp in experiences:
                exp_data.append({
                    'title': exp.title,
                    'company': exp.company,
                    'description': exp.description,
                    'skills': [skill.skill_name for skill in exp.skills]
                })
                
            skill_names = [skill.skill_name for skill in skills]
            
        # Generate analysis using AI
        analysis = await ai_engine.generate(
            prompt=f"""Analyze this job posting based on the candidate's profile:

Job Details:
Title: {job_info.get('title')}
Company: {job_info.get('company')}
Description: {job_info.get('description')}

Candidate Experience:
{exp_data[:3]}  # Most recent experiences

Skills: {', '.join(skill_names[:10])}

Analyze:
1. Key requirements and qualifications
2. Culture and work environment indicators
3. Career growth potential
4. Location/remote work requirements
5. Company size/maturity
6. Expected years of experience
7. Potential skill gaps""",
            output_type=JobAnalysis
        )
        
        if analysis:
            monitoring.track_success('job_analysis')
            return analysis
            
        monitoring.track_failure('job_analysis')
        logger.error("Failed to generate job analysis")
        return None
        
    except Exception as e:
        monitoring.track_error('job_analysis', str(e))
        logger.error(f"Error analyzing job: {str(e)}")
        return None

async def get_glassdoor_info(company_name: str) -> Optional[GlassdoorInfo]:
    """Get company information from Glassdoor."""
    try:
        monitoring.increment('glassdoor_lookup')
        logger.info(f"Looking up company on Glassdoor: {company_name}")
        
        # Search Glassdoor using web scraper
        url = f"https://www.glassdoor.com/Search/results.htm?keyword={company_name}"
        soup = await web_scraper.get_soup(url)
        
        if not soup:
            monitoring.track_failure('glassdoor_lookup')
            return None
            
        # Extract company info
        company_link = soup.find('a', {'class': 'company-tile'})
        if not company_link:
            monitoring.track_failure('glassdoor_lookup')
            return None
            
        company_url = f"https://www.glassdoor.com{company_link['href']}"
        company_soup = await web_scraper.get_soup(company_url)
        
        if not company_soup:
            monitoring.track_failure('glassdoor_lookup')
            return None
            
        # Parse company data
        info = GlassdoorInfo(
            rating=company_soup.find('div', {'class': 'rating'}).text.strip(),
            size=company_soup.find('div', {'class': 'size'}).text.strip(),
            industry=company_soup.find('div', {'class': 'industry'}).text.strip(),
            founded=company_soup.find('div', {'class': 'founded'}).text.strip(),
            benefits=company_soup.find('div', {'class': 'benefits'}).text.strip()
        )
        
        monitoring.track_success('glassdoor_lookup')
        return info
        
    except Exception as e:
        monitoring.track_error('glassdoor_lookup', str(e))
        logger.error(f"Error getting Glassdoor info: {str(e)}")
        return None

async def analyze_jobs_batch(jobs: List[Dict]) -> Dict[str, JobAnalysis]:
    """Analyze a batch of jobs and return analysis results."""
    try:
        logger.info(f"Analyzing batch of {len(jobs)} jobs")
        monitoring.increment('batch_analysis')
        
        results = {}
        for job in jobs:
            analysis = await analyze_job_with_gemini(job)
            if analysis:
                results[job['url']] = analysis
                
                # Get additional company info
                company_info = await get_glassdoor_info(job['company'])
                if company_info:
                    results[job['url']].company_analysis = CompanyAnalysis(
                        glassdoor_info=company_info
                    )
                    
        monitoring.track_success('batch_analysis')
        return results
        
    except Exception as e:
        monitoring.track_error('batch_analysis', str(e))
        logger.error(f"Error in batch analysis: {str(e)}")
        return {}