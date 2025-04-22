import os
import json
import re
from dotenv import load_dotenv
import google.generativeai as genai
from scripts.logging_utils import setup_logging
from scripts.models import Experience, Skill, TargetRole, JobCache
from scripts.utils import session_scope
import requests
from bs4 import BeautifulSoup
import urllib.parse
from structured_prompt import StructuredPrompt

logger = setup_logging('job_analysis')

# Configure Google Generative AI
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

# Initialize StructuredPrompt
structured_prompt = StructuredPrompt()

def analyze_job_with_gemini(job_info):
    """Use Gemini to analyze job posting and provide insights"""
    logger.info(f"Analyzing job with Gemini: {job_info['title']} at {job_info['company']}")
    
    # Check cache first
    cache_key = f"{job_info['title']}::{job_info['company']}"
    if hasattr(analyze_job_with_gemini, 'analysis_cache'):
        if cache_key in analyze_job_with_gemini.analysis_cache:
            logger.debug(f"Using cached analysis for {cache_key}")
            return analyze_job_with_gemini.analysis_cache[cache_key]
    else:
        analyze_job_with_gemini.analysis_cache = {}

    # Get Glassdoor data first
    glassdoor_info = get_glassdoor_info(job_info['company'])

    # Get candidate profile data from the database
    try:
        # Get skills and experience from database
        skill_list = []
        experience_summary = ""
        
        with session_scope() as session:
            # Get skills
            skills = session.query(Skill).all()
            skill_list = [skill.skill_name for skill in skills]
            
            # Get summary of experiences
            experiences = session.query(Experience).order_by(
                Experience.end_date.desc(),
                Experience.start_date.desc()
            ).limit(5).all()
            
            for exp in experiences:
                experience_summary += f"- {exp.title} at {exp.company}\n"
        
        # Get target roles
        target_roles = []
        with session_scope() as session:
            roles = session.query(TargetRole).order_by(TargetRole.priority).limit(3).all()
            target_roles = [role.role_name for role in roles]
    except Exception as e:
        logger.error(f"Error fetching candidate profile: {str(e)}")
        skill_list = ["Technical Professional"]
        target_roles = ["Technical Role"]
        experience_summary = "Professional with relevant experience"

    # Create a formatted skills section
    skill_text = "- " + "\n- ".join(skill_list[:15]) if len(skill_list) > 15 else "- " + "\n- ".join(skill_list)

    # Build Glassdoor context
    glassdoor_context = ""
    if glassdoor_info:
        glassdoor_context = f"""
Company Information from Glassdoor:
- Size: {glassdoor_info['company_size']}
- Industry: {glassdoor_info['industry']}
- Founded: {glassdoor_info['year_founded']}
- Revenue: {glassdoor_info['revenue']}
- Rating: {glassdoor_info['glassdoor_rating']}
- Employees: {glassdoor_info['employee_count']}
- Type: {glassdoor_info['company_type']}
- Growth Indicators: {', '.join(glassdoor_info['growth_indicators'])}"""

    # Define expected structure
    expected_structure = {
        "match_score": float,
        "key_requirements": [str],
        "culture_indicators": [str],
        "career_growth_potential": str,
        "application_priority": str,
        "location_type": str,
        "total_years_experience": int,
        "candidate_gaps": [str],
        "company_overview": {
            "industry": str,
            "size": str,
            "stability": str,
            "glassdoor_rating": str,
            "employee_count": str,
            "year_founded": str,
            "growth_stage": str,
            "market_position": str,
            "development_opportunities": [str]
        }
    }

    # Example data structure
    example_data = {
        "match_score": 85.5,
        "key_requirements": ["Python", "Cloud Infrastructure", "DevOps"],
        "culture_indicators": ["Remote-friendly", "Collaborative"],
        "career_growth_potential": "high - clear path to technical leadership",
        "application_priority": "high",
        "location_type": "remote",
        "total_years_experience": 5,
        "candidate_gaps": ["Kubernetes experience"],
        "company_overview": {
            "industry": "Technology",
            "size": "midsize",
            "stability": "high",
            "glassdoor_rating": "4.2",
            "employee_count": "500-1000",
            "year_founded": "2015",
            "growth_stage": "growth",
            "market_position": "challenger",
            "development_opportunities": ["Technical leadership", "Cloud architecture"]
        }
    }

    # Get structured response
    analysis = structured_prompt.get_structured_response(
        prompt=f"""Analyze this job posting and evaluate how well it matches the candidate's profile.
Use the provided Glassdoor company information to enhance your analysis.

Job Details:
Title: {job_info['title']}
Company: {job_info['company']}
Description: {job_info['description']}
{glassdoor_context}

Candidate Profile:
Target Roles: {', '.join(target_roles)}

Recent Experience:
{experience_summary}

Candidate Skills:
{skill_text}""",
        expected_structure=expected_structure,
        example_data=example_data
    )

    if analysis:
        analyze_job_with_gemini.analysis_cache[cache_key] = analysis
        logger.info(f"Successfully analyzed job: {job_info['title']} at {job_info['company']}")
        return analysis

    # Return default analysis on any error
    default_analysis = {
        "match_score": 0,
        "key_requirements": [],
        "culture_indicators": [],
        "career_growth_potential": "unknown",
        "application_priority": "low",
        "location_type": "unknown",
        "total_years_experience": 0,
        "candidate_gaps": [],
        "company_overview": {
            "industry": "unknown",
            "size": "unknown",
            "stability": "unknown",
            "glassdoor_rating": "unknown",
            "employee_count": "unknown",
            "year_founded": "unknown",
            "growth_stage": "unknown",
            "market_position": "unknown",
            "development_opportunities": []
        }
    }
    analyze_job_with_gemini.analysis_cache[cache_key] = default_analysis
    return default_analysis

def get_glassdoor_info(company_name):
    """Search Glassdoor for company information"""
    logger.info(f"Searching Glassdoor for company: {company_name}")
    try:
        # Construct search URL
        search_url = f"https://www.glassdoor.com/Search/results.htm?keyword={urllib.parse.quote(company_name)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        # Get search results page
        response = requests.get(search_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to search Glassdoor: {response.status_code}")
            return None

        # Define expected structure
        expected_structure = {
            "company_size": str,
            "industry": str,
            "year_founded": str,
            "headquarters": str,
            "revenue": str,
            "glassdoor_rating": str,
            "employee_count": str,
            "company_type": str,
            "growth_indicators": [str]
        }

        # Example data structure
        example_data = {
            "company_size": "large",
            "industry": "Technology",
            "year_founded": "2004",
            "headquarters": "Mountain View, CA",
            "revenue": "$100B+",
            "glassdoor_rating": "4.5",
            "employee_count": "50000+",
            "company_type": "public",
            "growth_indicators": [
                "15% revenue growth",
                "aggressive hiring",
                "market expansion"
            ]
        }

        # Get structured response
        glassdoor_data = structured_prompt.get_structured_response(
            prompt=f"""Extract company information from this Glassdoor search results page HTML.
Parse the company details into a structured format.

If you can't find specific information, use "unknown" as the value.

HTML content:
{response.text}""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if glassdoor_data:
            logger.info(f"Successfully retrieved Glassdoor data for {company_name}")
            return glassdoor_data
            
        logger.error("Failed to parse Glassdoor data")
        return None
            
    except Exception as e:
        logger.error(f"Error getting Glassdoor info: {str(e)}")
        return None

def analyze_jobs_batch(jobs):
    """Analyze a batch of jobs and return the analysis results"""
    logger.info(f"Analyzing batch of {len(jobs)} jobs")
    analyzed_jobs = {}
    
    for job in jobs:
        url = job['url']
        if url not in analyzed_jobs:
            analysis = analyze_job_with_gemini(job)
            if analysis:
                # Merge job details with analysis
                analyzed_job = job.copy()
                analyzed_job.update(analysis)
                analyzed_jobs[url] = analyzed_job
    
    # Sort by match score and application priority
    priority_scores = {'high': 3, 'medium': 2, 'low': 1}
    sorted_jobs = list(analyzed_jobs.values())
    sorted_jobs.sort(key=lambda x: (
        x.get('match_score', 0),
        priority_scores.get(x.get('application_priority', 'low'), 0)
    ), reverse=True)
    
    return sorted_jobs, analyzed_jobs