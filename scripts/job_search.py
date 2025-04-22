import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re
import time
import random
from logging_utils import setup_logging
from models import JobCache, JobApplication
from utils import session_scope

logger = setup_logging('job_search')

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
                    'match_score': job.match_score,
                    'application_priority': job.application_priority,
                    'key_requirements': json.loads(job.key_requirements) if job.key_requirements else [],
                    'culture_indicators': json.loads(job.culture_indicators) if job.culture_indicators else [],
                    'career_growth_potential': job.career_growth_potential,
                    'search_query': job.search_query
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
    """Just collect job links and basic info without analysis"""
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
        soup = BeautifulSoup(response.text, 'html.parser')
        
        jobs = []
        seen_urls = set()  # Track URLs within this query
        job_cards = soup.find_all("div", class_="base-card")
        
        for card in job_cards:
            try:
                title_elem = card.find("h3", class_="base-search-card__title")
                company_elem = card.find("h4", class_="base-search-card__subtitle")
                link_elem = card.find("a", class_="base-card__full-link")
                description_elem = card.find("div", class_="base-search-card__metadata")
                
                if title_elem and company_elem and link_elem:
                    url = normalize_linkedin_url(link_elem.get("href"))
                    
                    # Skip if we've seen this URL in this query
                    if url in seen_urls:
                        continue
                        
                    seen_urls.add(url)
                    jobs.append({
                        "url": url,
                        "title": title_elem.get_text(strip=True),
                        "company": company_elem.get_text(strip=True),
                        "description": description_elem.get_text(strip=True) if description_elem else "",
                        "search_query": query
                    })
                    
                    if len(jobs) >= limit:
                        break
            except Exception as e:
                logger.error(f"Error parsing job card: {str(e)}")
                continue
        
        logger.info(f"Collected {len(jobs)} unique job links for query: {query}")
        return jobs
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

    # Load profile data for personalization
    profile_path = os.path.join(root_dir, 'inputs', 'profile.json')
    try:
        with open(profile_path) as f:
            profile_data = json.load(f)
        contact_info = profile_data.get('contact_info', {})
    except FileNotFoundError:
        logger.error(f"Profile data not found at {profile_path}")
        contact_info = {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing profile data: {str(e)}")
        contact_info = {}
    
    # Add contact info to all jobs
    for job in jobs:
        job['contact_info'] = contact_info
    
    # Return filtered jobs (analysis will be done separately)
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
                
                # Check if job exists
                cached_job = session.query(JobCache).filter_by(url=url).first()
                
                if cached_job:
                    # Update existing job
                    cached_job.last_seen_date = datetime.now().strftime("%Y-%m-%d")
                    cached_job.match_score = analysis.get('match_score', 0)
                    cached_job.application_priority = analysis.get('application_priority', 'low')
                    cached_job.key_requirements = json.dumps(analysis.get('key_requirements', []))
                    cached_job.culture_indicators = json.dumps(analysis.get('culture_indicators', []))
                    cached_job.career_growth_potential = analysis.get('career_growth_potential', 'unknown')
                    updated_count += 1
                else:
                    # Insert new job
                    new_job = JobCache(
                        url=url,
                        title=job['title'],
                        company=job['company'],
                        description=job['description'],
                        first_seen_date=datetime.now().strftime("%Y-%m-%d"),
                        last_seen_date=datetime.now().strftime("%Y-%m-%d"),
                        match_score=analysis.get('match_score', 0),
                        application_priority=analysis.get('application_priority', 'low'),
                        key_requirements=json.dumps(analysis.get('key_requirements', [])),
                        culture_indicators=json.dumps(analysis.get('culture_indicators', [])),
                        career_growth_potential=analysis.get('career_growth_potential', 'unknown'),
                        search_query=job['search_query']
                    )
                    session.add(new_job)
                    new_count += 1
            
            logger.info(f"Updated {updated_count} jobs and added {new_count} new jobs to cache")
    except Exception as e:
        logger.error(f"Error updating job cache: {str(e)}")
        raise