"""Job analysis and scoring functionality."""

import os
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv

from ..core.ai import StructuredPrompt
from ..core.logging import setup_logging
from ..core.database import JobCache, get_session
from .common import JobInfo

logger = setup_logging('job_analysis')

# Configure Google Generative AI
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

def analyze_job_with_gemini(job_info: JobInfo) -> Optional[Dict]:
    """Use Gemini to analyze job posting and provide insights"""
    try:
        structured_prompt = StructuredPrompt()

        expected_structure = {
            "match_score": float,
            "key_requirements": [str],
            "culture_indicators": [str],
            "career_growth_potential": str,
            "total_years_experience": int,
            "candidate_gaps": [str],
            "location_type": str,
            "company_size": str,
            "company_stability": str,
            "development_opportunities": [str],
            "reasoning": str
        }

        example_data = {
            "match_score": 0.85,
            "key_requirements": [
                "5+ years cloud infrastructure experience",
                "Expert level Terraform knowledge",
                "CI/CD pipeline development"
            ],
            "culture_indicators": [
                "Strong emphasis on collaboration",
                "Focus on continuous learning",
                "Remote-friendly environment"
            ],
            "career_growth_potential": "high",
            "total_years_experience": 5,
            "candidate_gaps": [
                "Limited experience with specific cloud provider",
                "No direct experience with required industry"
            ],
            "location_type": "hybrid",
            "company_size": "midsize",
            "company_stability": "high",
            "development_opportunities": [
                "Leadership track available",
                "Training budget provided",
                "Mentorship program"
            ],
            "reasoning": "Strong match based on technical skills and culture fit..."
        }

        analysis = structured_prompt.get_structured_response(
            prompt=f"""Analyze this job posting. Consider both explicit requirements and implicit indicators.
Focus on technical requirements, company culture, growth potential, and potential skill gaps.

Job Title: {job_info.title}
Company: {job_info.company}
Description: {job_info.description}

Analyze the posting and return a structured analysis including:
1. Overall match score (0.0-1.0)
2. Key technical and non-technical requirements
3. Culture indicators from the job description
4. Career growth potential (high/medium/low)
5. Total years experience required
6. Any potential gaps in candidate qualifications
7. Location type (remote/hybrid/onsite)
8. Company size indication (startup/midsize/large/enterprise)
9. Company stability assessment (high/medium/low)
10. Development and growth opportunities
11. Reasoning for the assessment

Return only the structured JSON response.""",
            expected_structure=expected_structure,
            example_data=example_data,
            temperature=0.2
        )

        if analysis:
            logger.info(f"Successfully analyzed job: {job_info.title} at {job_info.company}")
            return analysis
        else:
            logger.error(f"Failed to analyze job: {job_info.title}")
            return None

    except Exception as e:
        logger.error(f"Error analyzing job: {str(e)}")
        return None

def get_glassdoor_info(company_name: str) -> Optional[Dict]:
    """Search Glassdoor for company information"""
    try:
        # Format search URL
        search_url = f"https://www.glassdoor.com/Search/results.htm?keyword={company_name}"
        
        # Set headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Get search results
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract company overview if found
        company_info = {
            'rating': None,
            'employee_count': None,
            'year_founded': None,
            'industry': None,
            'website': None
        }
        
        # Note: This is a simplified version. In practice, you'd need to handle
        # rate limiting, different page structures, etc.
        
        return company_info if any(company_info.values()) else None
        
    except Exception as e:
        logger.error(f"Error getting Glassdoor info for {company_name}: {str(e)}")
        return None

def analyze_jobs_batch(jobs: List[JobInfo]) -> List[Dict]:
    """Analyze a batch of jobs and return the analysis results"""
    results = []
    
    for job in jobs:
        # Get job analysis
        analysis = analyze_job_with_gemini(job)
        if not analysis:
            continue
            
        # Enrich with Glassdoor data
        glassdoor_info = get_glassdoor_info(job.company)
        if glassdoor_info:
            analysis.update(glassdoor_info)
            
        # Store result
        results.append({
            'url': job.url,
            'title': job.title,
            'company': job.company,
            'analysis': analysis
        })
        
    return results

def save_job_analysis(job_url: str, analysis: Dict) -> bool:
    """Save job analysis results to database"""
    try:
        with get_session() as session:
            job = session.query(JobCache).filter_by(url=job_url).first()
            if not job:
                logger.error(f"Job not found in cache: {job_url}")
                return False
                
            # Update job with analysis
            job.match_score = analysis.get('match_score')
            job.key_requirements = analysis.get('key_requirements')
            job.culture_indicators = analysis.get('culture_indicators')
            job.career_growth_potential = analysis.get('career_growth_potential')
            job.total_years_experience = analysis.get('total_years_experience')
            job.candidate_gaps = analysis.get('candidate_gaps')
            job.location_type = analysis.get('location_type')
            job.company_size = analysis.get('company_size')
            job.company_stability = analysis.get('company_stability')
            job.development_opportunities = analysis.get('development_opportunities')
            
            # Update with Glassdoor info if available
            if analysis.get('glassdoor_rating'):
                job.glassdoor_rating = analysis['glassdoor_rating']
            if analysis.get('employee_count'):
                job.employee_count = analysis['employee_count']
            if analysis.get('year_founded'):
                job.year_founded = analysis['year_founded']
                
            logger.info(f"Saved analysis for job: {job_url}")
            return True
            
    except Exception as e:
        logger.error(f"Error saving job analysis: {str(e)}")
        return False