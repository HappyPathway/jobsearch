import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re
import time
import random
import google.generativeai as genai
from dotenv import load_dotenv
from logging_utils import setup_logging
from models import JobCache, JobApplication, Base, get_engine
from utils import session_scope
from structured_prompt import StructuredPrompt

logger = setup_logging('job_search')

# Configure Gemini
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

# Initialize StructuredPrompt
structured_prompt = StructuredPrompt()

def ensure_database():
    """Ensure database exists and has correct schema"""
    try:
        # This will create tables if they don't exist
        Base.metadata.create_all(get_engine())
        logger.info("Database schema verified")
        return True
    except Exception as e:
        logger.error(f"Error ensuring database schema: {str(e)}")
        return False

# Ensure database is initialized before running job search
if not ensure_database():
    raise RuntimeError("Failed to initialize database")

def normalize_linkedin_url(url):
    """Normalize LinkedIn job URLs to ensure consistent matching"""
    # Extract just the job ID portion to handle different URL formats
    match = re.search(r'(?:jobs|view)/(\d+)', url)
    if match:
        return f"https://www.linkedin.com/jobs/view/{match.group(1)}"
    return url

def normalize_title(title):
    """Normalize job titles for better matching"""
    if not title:
        return ""
    
    # Convert to lowercase
    title = title.lower()
    
    # Remove location-specific info in parentheses
    title = re.sub(r'\s*\([^)]*\)', '', title)
    
    # Remove common location prefixes/suffixes
    title = re.sub(r'\s*(- remote|\(remote\)|remote|onsite|hybrid|\d+%|\bUS\b)', '', title, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title

def deduplicate_jobs(jobs):
    """Remove duplicate job postings based on title + company, even with different locations"""
    logger.info(f"Deduplicating {len(jobs)} job listings")
    
    unique_jobs = []
    seen_jobs = {}  # Dictionary to track {(normalized_title, company): job_index}
    
    for job in jobs:
        # Create a normalized key for matching
        normalized_title = normalize_title(job.get('title', ''))
        company = job.get('company', '').lower()
        key = (normalized_title, company)
        
        # If we've seen this job before
        if key in seen_jobs:
            existing_index = seen_jobs[key]
            existing_job = unique_jobs[existing_index]
            
            # Check if we should replace with this one (e.g., if this is remote and other isn't)
            desc_lower = job.get('description', '').lower()
            existing_desc = existing_job.get('description', '').lower()
            
            # Prefer remote positions or those with more details
            if ('remote' in desc_lower and 'remote' not in existing_desc) or \
               (len(desc_lower) > len(existing_desc)):
                unique_jobs[existing_index] = job
                logger.info(f"Replaced duplicate: '{existing_job['title']}' with '{job['title']}' at {company}")
            else:
                logger.info(f"Skipped duplicate: '{job['title']}' matches '{existing_job['title']}' at {company}")
        else:
            # New unique job
            seen_jobs[key] = len(unique_jobs)
            unique_jobs.append(job)
    
    logger.info(f"Deduplicated to {len(unique_jobs)} unique job listings (removed {len(jobs) - len(unique_jobs)} duplicates)")
    return unique_jobs

def get_cached_jobs():
    """Get all cached jobs from the database"""
    logger.info("Retrieving cached jobs")
    try:
        with session_scope() as session:
            jobs = session.query(JobCache).all()
            cached_jobs = {
                job.url: {
                    'title': job.title,
                    'company': job.company,
                    'description': job.description,
                    'first_seen_date': job.first_seen_date,
                    'last_seen_date': job.last_seen_date,
                    'location': job.location,
                    'post_date': job.post_date,
                    'search_query': job.search_query,
                    
                    # Core analysis fields
                    'match_score': job.match_score,
                    'application_priority': job.application_priority,
                    'key_requirements': json.loads(job.key_requirements) if job.key_requirements else [],
                    'culture_indicators': json.loads(job.culture_indicators) if job.culture_indicators else [],
                    'career_growth_potential': job.career_growth_potential,
                    
                    # Enhanced analysis fields
                    'total_years_experience': job.total_years_experience,
                    'candidate_gaps': json.loads(job.candidate_gaps) if job.candidate_gaps else [],
                    'location_type': job.location_type,
                    
                    # Company overview fields
                    'company_size': job.company_size,
                    'company_stability': job.company_stability,
                    'glassdoor_rating': job.glassdoor_rating,
                    'employee_count': job.employee_count,
                    'year_founded': job.year_founded,
                    'growth_stage': job.growth_stage,
                    'market_position': job.market_position,
                    'development_opportunities': json.loads(job.development_opportunities) if job.development_opportunities else []
                } for job in jobs
            }
            logger.info(f"Retrieved {len(cached_jobs)} cached jobs")
            return cached_jobs
    except Exception as e:
        logger.error(f"Error retrieving cached jobs: {str(e)}")
        return {}

def get_applied_jobs():
    """Get all jobs that have been applied to"""
    logger.info("Retrieving applied jobs")
    try:
        with session_scope() as session:
            applications = session.query(JobApplication).join(JobCache).all()
            applied_jobs = {
                app.job.url: {
                    'application_date': app.application_date,
                    'status': app.status
                } for app in applications
            }
            logger.info(f"Retrieved {len(applied_jobs)} applied jobs")
            return applied_jobs
    except Exception as e:
        logger.error(f"Error retrieving applied jobs: {str(e)}")
        return {}

def collect_job_links(query, location="United States", limit=5):
    """Collect job links and basic info using Gemini for parsing"""
    logger.info(f"Collecting job links for query: {query}")
    try:
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
        
        response = requests.get(base_url, params=params, headers=headers)
        
        # Define expected structure
        expected_structure = [{
            "url": str,
            "title": str,
            "company": str,
            "location": str,
            "post_date": str,
            "description": str
        }]

        # Example data
        example_data = [{
            "url": "https://www.linkedin.com/jobs/view/123456",
            "title": "Senior Cloud Architect",
            "company": "Tech Corp",
            "location": "Remote",
            "post_date": "2 days ago",
            "description": "Looking for an experienced architect..."
        }]

        # Initialize StructuredPrompt
        structured_prompt = StructuredPrompt()

        # Get structured response
        jobs = structured_prompt.get_structured_response(
            prompt=f"""Extract job listings from this LinkedIn search results page HTML.
Each job listing should have a URL, title, company name, location, posting date, and description.
Ensure location and post_date are separate fields, not combined in the description.

HTML content:
{response.text}""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if not jobs:
            logger.error("Failed to parse job listings")
            return []

        # Clean up and deduplicate jobs
        cleaned_jobs = []
        seen_urls = set()
        
        for job in jobs:
            # Normalize URL
            url = job['url']
            if not url.startswith('http'):
                url = f"https://www.linkedin.com{url}"
            
            if url not in seen_urls:
                seen_urls.add(url)
                job['url'] = url
                cleaned_jobs.append(job)
                
                if len(cleaned_jobs) >= limit:
                    break

        logger.info(f"Found {len(cleaned_jobs)} unique jobs")
        return cleaned_jobs

    except Exception as e:
        logger.error(f"Error collecting job links: {str(e)}")
        return []

def search_linkedin_jobs(query, location="United States", limit=2):
    """Search LinkedIn jobs, using cache for known jobs"""
    logger.info(f"Searching LinkedIn jobs for query: {query}, location: {location}, limit: {limit}")
    
    # Get cached and applied jobs
    cached_jobs = get_cached_jobs()
    applied_jobs = get_applied_jobs()
    
    # Get one week ago date
    one_week_ago = datetime.now() - timedelta(days=7)
    
    # Set up root directory
    root_dir = Path(__file__).resolve().parent.parent
    
    # Collect new job links - request more to account for filtering and deduplication
    jobs = collect_job_links(query, location, limit * 3)
    
    # Filter out jobs we've already applied to, normalize URLs, and apply one-week filter
    jobs = [
        job for job in jobs 
        if normalize_linkedin_url(job['url']) not in {normalize_linkedin_url(url) for url in applied_jobs.keys()} 
        and (
            'first_seen_date' not in job 
            or datetime.strptime(job['first_seen_date'], '%Y-%m-%d') > one_week_ago
        )
    ]

    # Deduplicate jobs based on title and company
    jobs = deduplicate_jobs(jobs)

    # Limit to requested number after deduplication
    jobs = jobs[:limit]
    
    logger.info(f"Returning {len(jobs)} filtered jobs for query: {query}")
    return jobs

def update_job_cache(jobs, analyzed_jobs):
    """Update the job cache with new or updated job information"""
    logger.info("Updating job cache")
    updated_count = 0
    new_count = 0
    
    try:
        with session_scope() as session:
            for job in jobs:
                url = job['url']
                analysis = analyzed_jobs.get(url, {})
                company_overview = analysis.get('company_overview', {})
                
                # Check if job exists
                cached_job = session.query(JobCache).filter_by(url=url).first()
                
                if cached_job:
                    # Update existing job
                    cached_job.last_seen_date = datetime.now().strftime("%Y-%m-%d")
                    cached_job.location = job.get('location', '')
                    cached_job.post_date = job.get('post_date', '')
                    cached_job.description = job.get('description', '')
                    
                    # Core analysis fields
                    cached_job.match_score = analysis.get('match_score', 0)
                    cached_job.application_priority = analysis.get('application_priority', 'low')
                    cached_job.key_requirements = json.dumps(analysis.get('key_requirements', []))
                    cached_job.culture_indicators = json.dumps(analysis.get('culture_indicators', []))
                    cached_job.career_growth_potential = analysis.get('career_growth_potential', 'unknown')
                    
                    # Enhanced analysis fields
                    cached_job.total_years_experience = analysis.get('total_years_experience', 0)
                    cached_job.candidate_gaps = json.dumps(analysis.get('candidate_gaps', []))
                    cached_job.location_type = analysis.get('location_type', 'unknown')
                    
                    # Company overview fields from Glassdoor/analysis
                    cached_job.company_size = company_overview.get('size', 'unknown')
                    cached_job.company_stability = company_overview.get('stability', 'unknown')
                    cached_job.glassdoor_rating = company_overview.get('glassdoor_rating', 'unknown')
                    cached_job.employee_count = company_overview.get('employee_count', 'unknown')
                    cached_job.year_founded = company_overview.get('year_founded', 'unknown')
                    cached_job.growth_stage = company_overview.get('growth_stage', 'unknown')
                    cached_job.market_position = company_overview.get('market_position', 'unknown')
                    cached_job.development_opportunities = json.dumps(company_overview.get('development_opportunities', []))
                    
                    updated_count += 1
                else:
                    # Insert new job
                    new_job = JobCache(
                        url=url,
                        title=job['title'],
                        company=job['company'],
                        location=job.get('location', ''),
                        post_date=job.get('post_date', ''),
                        description=job.get('description', ''),
                        first_seen_date=datetime.now().strftime("%Y-%m-%d"),
                        last_seen_date=datetime.now().strftime("%Y-%m-%d"),
                        search_query=job['search_query'],
                        
                        # Core analysis fields
                        match_score=analysis.get('match_score', 0),
                        application_priority=analysis.get('application_priority', 'low'),
                        key_requirements=json.dumps(analysis.get('key_requirements', [])),
                        culture_indicators=json.dumps(analysis.get('culture_indicators', [])),
                        career_growth_potential=analysis.get('career_growth_potential', 'unknown'),
                        
                        # Enhanced analysis fields
                        total_years_experience=analysis.get('total_years_experience', 0),
                        candidate_gaps=json.dumps(analysis.get('candidate_gaps', [])),
                        location_type=analysis.get('location_type', 'unknown'),
                        
                        # Company overview fields from Glassdoor/analysis
                        company_size=company_overview.get('size', 'unknown'),
                        company_stability=company_overview.get('stability', 'unknown'),
                        glassdoor_rating=company_overview.get('glassdoor_rating', 'unknown'),
                        employee_count=company_overview.get('employee_count', 'unknown'),
                        year_founded=company_overview.get('year_founded', 'unknown'),
                        growth_stage=company_overview.get('growth_stage', 'unknown'),
                        market_position=company_overview.get('market_position', 'unknown'),
                        development_opportunities=json.dumps(company_overview.get('development_opportunities', []))
                    )
                    session.add(new_job)
                    new_count += 1
            
            logger.info(f"Updated {updated_count} jobs and added {new_count} new jobs to cache")
    except Exception as e:
        logger.error(f"Error updating job cache: {str(e)}")
        raise