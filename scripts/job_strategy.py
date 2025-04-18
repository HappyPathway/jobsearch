import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import google.generativeai as genai
from dotenv import load_dotenv
from models import Experience, Skill, TargetRole, JobCache, JobApplication
from logging_utils import setup_logging
from utils import session_scope
import re
import requests
from bs4 import BeautifulSoup
import time
import random
import argparse
import generate_documents

logger = setup_logging('job_strategy')

# Configure Google Generative AI
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

def normalize_linkedin_url(url):
    """Normalize LinkedIn job URLs to ensure consistent matching"""
    # Extract just the job ID portion to handle different URL formats
    match = re.search(r'(?:jobs|view)/(\d+)', url)
    if match:
        return f"https://www.linkedin.com/jobs/view/{match.group(1)}"
    return url

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
    
    # Collect new job links - request more to account for filtering
    jobs = collect_job_links(query, location, limit * 2)
    
    # Filter out jobs we've already applied to, normalize URLs, and apply one-week filter
    jobs = [
        job for job in jobs 
        if normalize_linkedin_url(job['url']) not in {normalize_linkedin_url(url) for url in applied_jobs.keys()} 
        and (
            'first_seen_date' not in job 
            or datetime.strptime(job['first_seen_date'], '%Y-%m-%d') > one_week_ago
        )
    ]

    # Track which jobs need analysis
    new_jobs = []
    analyzed_jobs = {}
    
    # Load profile data for personalization
    with open(os.path.join(root_dir, 'docs', 'profile.json')) as f:
        profile_data = json.load(f)
    contact_info = profile_data.get('contact_info', {})
    
    # Normalize URLs for comparison
    normalized_cache = {normalize_linkedin_url(url): data for url, data in cached_jobs.items()}
    
    for job in jobs:
        url = normalize_linkedin_url(job['url'])
        if url in normalized_cache:
            # Use cached analysis but update last seen date
            cached_data = normalized_cache[url]
            cached_data['contact_info'] = contact_info  # Add contact info
            analyzed_jobs[url] = cached_data
            logger.debug(f"Using cached analysis for {job['title']} at {job['company']}")
        else:
            job['contact_info'] = contact_info  # Add contact info to new jobs
            new_jobs.append(job)
            logger.debug(f"Will analyze new job: {job['title']} at {job['company']}")
    
    # Analyze only truly new jobs
    analyzed_urls = set()  # Track which jobs we've analyzed to prevent duplicates
    for job in new_jobs:
        url = normalize_linkedin_url(job['url'])
        if url not in analyzed_urls:
            analysis = analyze_job_with_gemini(job)
            if analysis:
                analyzed_jobs[url] = analysis
                analyzed_urls.add(url)
    
    # Update cache with new information
    update_job_cache(jobs, analyzed_jobs)
    
    # Combine job info with analysis and sort by match score
    results = []
    seen_urls = set()  # Track which jobs we've added to results
    
    for job in jobs:
        url = normalize_linkedin_url(job['url'])
        if url not in seen_urls and url in analyzed_jobs:
            job_info = job.copy()
            job_info.update(analyzed_jobs[url])
            results.append(job_info)
            seen_urls.add(url)
    
    # Sort by match score and application priority
    priority_scores = {'high': 3, 'medium': 2, 'low': 1}
    results.sort(key=lambda x: (
        x.get('match_score', 0),
        priority_scores.get(x.get('application_priority', 'low'), 0)
    ), reverse=True)
    
    # Return top N unique results
    top_results = results[:limit]
    logger.info(f"Returning top {len(top_results)} unique jobs for query: {query} (from {len(results)} total)")
    return top_results

def analyze_job_with_gemini(job_info):
    """Use Gemini to analyze job posting and provide insights"""
    logger.info(f"Analyzing job with Gemini: {job_info['title']} at {job_info['company']}")
    
    # Check if we've already analyzed this job in this session
    cache_key = f"{job_info['title']}::{job_info['company']}"
    if hasattr(analyze_job_with_gemini, 'analysis_cache'):
        if cache_key in analyze_job_with_gemini.analysis_cache:
            logger.debug(f"Using cached analysis for {cache_key}")
            return analyze_job_with_gemini.analysis_cache[cache_key]
    else:
        analyze_job_with_gemini.analysis_cache = {}

    prompt = f"""You are a job analysis expert. Analyze this job posting and return ONLY a valid JSON object with no additional text or formatting.

Job Details:
Title: {job_info['title']}
Company: {job_info['company']}
Description: {job_info['description']}

Required JSON format (replace with actual values, keep structure exactly as shown):
{{
    "match_score": 75,
    "key_requirements": [
        "requirement 1",
        "requirement 2",
        "requirement 3"
    ],
    "culture_indicators": [
        "indicator 1",
        "indicator 2"
    ],
    "career_growth_potential": "high - explanation here",
    "application_priority": "high"
}}"""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1000,
                "temperature": 0.1,
            }
        )
        
        # Clean up the response
        json_str = response.text.strip()
        json_str = re.sub(r'^```.*?\n', '', json_str)  # Remove opening ```json
        json_str = re.sub(r'\n```$', '', json_str)     # Remove closing ```
        
        # Try to extract just the JSON object if there's other text
        match = re.search(r'({[\s\S]*})', json_str)
        if match:
            json_str = match.group(1)
        
        try:
            # Parse and validate the JSON
            analysis = json.loads(json_str)
            
            # Ensure required fields exist with correct types
            required_fields = {
                'match_score': 0,  # Default values
                'key_requirements': [],
                'culture_indicators': [],
                'career_growth_potential': 'unknown',
                'application_priority': 'low'
            }
            
            for field, default in required_fields.items():
                if field not in analysis:
                    analysis[field] = default
            
            # Normalize match_score to 0-100
            try:
                analysis['match_score'] = max(0, min(100, float(analysis['match_score'])))
            except (ValueError, TypeError):
                analysis['match_score'] = 0
            
            # Ensure lists are lists and have reasonable lengths
            if not isinstance(analysis['key_requirements'], list):
                analysis['key_requirements'] = []
            analysis['key_requirements'] = [str(req) for req in analysis['key_requirements'][:5]]  # Max 5 requirements, ensure strings
            
            if not isinstance(analysis['culture_indicators'], list):
                analysis['culture_indicators'] = []
            analysis['culture_indicators'] = [str(ind) for ind in analysis['culture_indicators'][:3]]  # Max 3 indicators, ensure strings
            
            # Normalize strings
            analysis['career_growth_potential'] = str(analysis['career_growth_potential']).lower()
            analysis['application_priority'] = str(analysis['application_priority']).lower()
            
            # Validate application priority
            if analysis['application_priority'] not in ['high', 'medium', 'low']:
                analysis['application_priority'] = 'low'
            
            # Cache the analysis for this session
            analyze_job_with_gemini.analysis_cache[cache_key] = analysis
            
            logger.info(f"Successfully analyzed job: {job_info['title']} at {job_info['company']}")
            return analysis
            
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing error: {str(je)}")
            logger.debug(f"Problematic JSON string: {json_str}")
    except Exception as e:
        logger.error(f"Error analyzing job with Gemini: {str(e)}")
    
    # Return default analysis on any error
    default_analysis = {
        "match_score": 0,
        "key_requirements": [],
        "culture_indicators": [],
        "career_growth_potential": "unknown",
        "application_priority": "low"
    }
    analyze_job_with_gemini.analysis_cache[cache_key] = default_analysis
    return default_analysis

def generate_documents_for_jobs(job_searches):
    """Generate tailored documents for high-priority jobs"""
    logger.info("Generating tailored documents for high-priority jobs")
    try:
        import generate_documents
        
        generated_docs = []
        for search in job_searches:
            for job in search['listings']:
                # Only generate documents for high-priority jobs
                if job.get('application_priority', '').lower() == 'high':
                    logger.info(f"Generating documents for {job['title']} at {job['company']}")
                    resume_path, cover_letter_path = generate_documents.generate_job_documents(job)
                    if resume_path and cover_letter_path:
                        generated_docs.append({
                            "job": job,
                            "resume": resume_path,
                            "cover_letter": cover_letter_path
                        })
        return generated_docs
    except Exception as e:
        logger.error(f"Failed to generate job strategy: {str(e)}")
        return []

def get_profile_data():
    """Retrieve profile data from the database"""
    logger.info("Retrieving profile data from database")
    try:
        with session_scope() as session:
            # Get experiences
            experiences = session.query(Experience).order_by(
                Experience.end_date.desc(),
                Experience.start_date.desc()
            ).all()
            
            exp_list = [
                {
                    "company": exp.company,
                    "title": exp.title,
                    "start_date": exp.start_date,
                    "end_date": exp.end_date,
                    "description": exp.description
                }
                for exp in experiences
            ]
            
            # Get skills
            skills = [skill.skill_name for skill in session.query(Skill).all()]
            
            logger.info(f"Retrieved {len(exp_list)} experiences and {len(skills)} skills")
            return exp_list, skills
    except Exception as e:
        logger.error(f"Error retrieving profile data: {str(e)}")
        raise

def get_target_roles():
    """Get target roles from database"""
    logger.info("Retrieving target roles from database")
    try:
        with session_scope() as session:
            roles = session.query(TargetRole).order_by(TargetRole.priority).all()
            role_list = [
                {
                    "name": role.role_name,
                    "priority": role.priority,
                    "match_score": role.match_score,
                    "reasoning": role.reasoning
                }
                for role in roles
            ]
            
            if not role_list:
                logger.warning("No target roles found in database, using defaults")
                role_list = [
                    {
                        "name": "Cloud Architect",
                        "priority": 1,
                        "match_score": 90,
                        "reasoning": "Default role - matches current experience"
                    },
                    {
                        "name": "Principal Cloud Engineer",
                        "priority": 2,
                        "match_score": 85,
                        "reasoning": "Default role - natural progression"
                    }
                ]
            
            logger.info(f"Retrieved {len(role_list)} target roles")
            return role_list
    except Exception as e:
        logger.error(f"Error retrieving target roles: {str(e)}")
        raise

def generate_daily_strategy(experiences, skills, job_limit=2):
    """Use Gemini to generate a personalized job search strategy"""
    logger.info("Generating daily job search strategy")
    current_role = experiences[0] if experiences else None
    
    job_searches = []
    target_roles = get_target_roles()
    
    for role in target_roles:
        jobs = search_linkedin_jobs(role['name'], limit=job_limit)
        if jobs:
            job_searches.append({
                "role": role['name'],
                "priority": role['priority'],
                "match_score": role['match_score'],
                "reasoning": role['reasoning'],
                "listings": jobs
            })
        time.sleep(random.uniform(1, 2))

    prompt = f"""As an expert career strategist, create a detailed daily job search strategy.
Use this professional's background to create a highly specific and actionable plan.
Return ONLY a JSON object with no additional text or formatting.

Current Role:
Company: {current_role['company'] if current_role else 'N/A'}
Title: {current_role['title'] if current_role else 'N/A'}

Key Skills: {', '.join(skills[:10])} (and {len(skills) - 10} more)

Recent Experience Highlights:
{experiences[0]['description'] if experiences else 'N/A'}

Available Job Opportunities:
{json.dumps(job_searches, indent=2)}

Required JSON format:
{{
    "daily_focus": {{
        "title": "Focus area for today (e.g. 'Review and Plan')",
        "reasoning": "Why this focus is important for today",
        "success_metrics": [
            "Specific measurable goal 1",
            "Specific measurable goal 2"
        ],
        "morning": [
            {{
                "task": "Review and prioritize job listings",
                "time": "30",
                "priority": "High",
                "reasoning": "Focuses efforts on promising opportunities"
            }}
        ],
        "afternoon": [
            {{
                "task": "Submit high-quality application",
                "time": "60",
                "priority": "High",
                "reasoning": "Maintains consistent progress"
            }}
        ]
    }},
    "target_roles": [
        {{
            "title": "Principal Cloud Architect",
            "reasoning": "Aligns with current experience and career goals",
            "key_skills_to_emphasize": [
                "Cloud Architecture",
                "Terraform",
                "Kubernetes"
            ],
            "suggested_companies": [
                "Example Corp",
                "Tech Inc"
            ],
            "current_opportunities": [
                {{
                    "title": "Exact job title",
                    "company": "Company name",
                    "url": "Full URL to job posting",
                    "notes": "Remote position, matches skill set"
                }}
            ]
        }}
    ],
    "networking_strategy": {{
        "platforms": ["LinkedIn"],
        "daily_connections": 3,
        "message_template": "Hi [Name],\\n\\nI noticed your experience in [area]. I'm currently exploring opportunities in [target role] and would love to connect and learn more about your work at [company].\\n\\nBest regards,\\n[Your name]",
        "target_individuals": [
            "Cloud Architects",
            "Hiring Managers",
            "Technical Recruiters"
        ]
    }},
    "skill_development": [
        {{
            "skill": "Advanced Terraform",
            "action": "Complete HashiCorp Certified: Terraform Associate certification",
            "timeline": "2 weeks",
            "status": "In Progress"
        }}
    ],
    "application_strategy": {{
        "daily_target": 1,
        "quality_checklist": [
            "Tailored resume and cover letter",
            "Quantifiable achievements highlighted",
            "Keywords optimized for ATS"
        ],
        "customization_points": [
            "Company culture alignment",
            "Specific project requirements",
            "Career goals alignment"
        ],
        "tracking_method": "Using spreadsheet with:\\n- Company name\\n- Role\\n- Application date\\n- Status\\n- Follow-up notes"
    }}
}}"""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.2,
            }
        )
        
        json_str = response.text.strip()
        json_str = re.sub(r'^```.*\n', '', json_str)
        json_str = re.sub(r'\n```$', '', json_str)
        
        match = re.search(r'({.*})', json_str, re.DOTALL)
        if match:
            json_str = match.group(1)
        
        strategy = json.loads(json_str)
        logger.info("Successfully generated daily strategy")
        return strategy
    except Exception as e:
        logger.error(f"Error generating strategy: {str(e)}")
        return None

def generate_weekly_focus():
    """Generate a weekly focus area based on the day of the week"""
    logger.info("Generating weekly focus")
    prompt = """Create a mapping of days of the week to job search focus areas.
Return only a JSON object with this structure:
{
    "Monday": {
        "focus": "main focus area",
        "reason": "why this focus is good for Monday",
        "success_metrics": ["metric1", "metric2"]
    },
    // ...repeat for all weekdays
}"""
    
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1000,
                "temperature": 0.1,
            }
        )
        
        json_str = response.text.strip()
        json_str = re.sub(r'^```.*\n', '', json_str)
        json_str = re.sub(r'\n```$', '', json_str)
        
        match = re.search(r'({.*})', json_str, re.DOTALL)
        if match:
            json_str = match.group(1)
        
        weekly_focus = json.loads(json_str)
        logger.info("Successfully generated weekly focus")
        return weekly_focus
    except Exception as e:
        logger.error(f"Error generating weekly focus: {str(e)}")
        return None

def format_strategy_output_plain(strategy, weekly_focus):
    """Format strategy output in plain text format for backwards compatibility"""
    output = []
    output.append(f"Job Search Strategy - {datetime.now().strftime('%Y-%m-%d')}")
    
    # Daily Focus
    daily_focus = strategy.get('daily_focus', {})
    output.append(f"\nToday's Focus: {daily_focus.get('title', 'Daily Planning')}")
    output.append(f"Reasoning: {daily_focus.get('reasoning', '')}")
    
    output.append("\nSuccess Metrics:")
    for metric in daily_focus.get('success_metrics', []):
        output.append(f"- {metric}")
    
    # Target Roles
    output.append("\nTarget Roles:")
    for role in strategy.get('target_roles', []):
        output.append(f"\n{role['title']}")
        output.append(f"Reasoning: {role.get('reasoning', '')}")
        output.append("\nKey Skills:")
        for skill in role.get('key_skills_to_emphasize', []):
            output.append(f"- {skill}")
        output.append("\nTarget Companies:")
        for company in role.get('suggested_companies', []):
            output.append(f"- {company}")
        if role.get('current_opportunities'):
            output.append("\nCurrent Opportunities:")
            for opp in role['current_opportunities']:
                output.append(f"- {opp['title']} at {opp['company']}")
                output.append(f"  URL: {opp.get('url', 'No URL')}")
    
    # Networking Strategy
    network = strategy.get('networking_strategy', {})
    output.append("\nNetworking Strategy:")
    output.append(f"Daily Connections Target: {network.get('daily_connections', 3)}")
    output.append("\nTarget Individuals:")
    for target in network.get('target_individuals', []):
        output.append(f"- {target}")
    
    # Skill Development
    output.append("\nSkill Development:")
    for skill in strategy.get('skill_development', []):
        output.append(f"\n- {skill['skill']}")
        output.append(f"  Goal: {skill['action']}")
        output.append(f"  Timeline: {skill['timeline']}")
        if skill.get('status'):
            output.append(f"  Status: {skill['status']}")
    
    # Application Strategy
    app_strategy = strategy.get('application_strategy', {})
    output.append("\nApplication Strategy:")
    output.append(f"Daily Target: {app_strategy.get('daily_target', 1)} application(s)")
    
    output.append("\nQuality Checklist:")
    for item in app_strategy.get('quality_checklist', []):
        output.append(f"- {item}")
    
    return "\n".join(output)

def format_strategy_output(strategy, weekly_focus):
    """Format strategy output in Markdown format with enhanced formatting"""
    current_date = datetime.now().strftime('%B %d, %Y')
    output = []
    
    # Header and Focus
    output.append(f"# Job Search Strategy - {current_date}\n")
    output.append(f"## Today's Focus: {strategy.get('daily_focus', {}).get('title', 'Daily Planning')}")
    output.append(f"*Why*: {strategy.get('daily_focus', {}).get('reasoning', '')}\n")
    
    # Success Metrics
    output.append("### Success Metrics")
    for metric in strategy.get('daily_focus', {}).get('success_metrics', []):
        output.append(f"- [ ] {metric}")
    output.append("")
    
    # Morning Tasks
    output.append("## Morning Tasks\n")
    output.append("### High Priority")
    for task in strategy.get('daily_focus', {}).get('morning', []):
        if task.get('priority') == 'High':
            output.append(f"1. **{task['task']}** ⏱️ {task['time']}min  ")
            output.append(f"   *Why*: {task['reasoning']}")
    
    output.append("\n### Medium Priority")
    for task in strategy.get('daily_focus', {}).get('morning', []):
        if task.get('priority') == 'Medium':
            output.append(f"1. **{task['task']}** ⏱️ {task['time']}min  ")
            output.append(f"   *Why*: {task['reasoning']}")
    output.append("")
    
    # Afternoon Tasks
    output.append("## Afternoon Tasks\n")
    output.append("### High Priority")
    for task in strategy.get('daily_focus', {}).get('afternoon', []):
        if task.get('priority') == 'High':
            output.append(f"1. **{task['task']}** ⏱️ {task['time']}min  ")
            output.append(f"   *Why*: {task['reasoning']}")
    
    output.append("\n### Medium Priority")
    for task in strategy.get('daily_focus', {}).get('afternoon', []):
        if task.get('priority') == 'Medium':
            output.append(f"1. **{task['task']}** ⏱️ {task['time']}min  ")
            output.append(f"   *Why*: {task['reasoning']}")
    output.append("")
    
    # Target Roles & Opportunities
    output.append("## Target Roles & Current Opportunities\n")
    for role in strategy.get('target_roles', []):
        output.append(f"### {role['title']}")
        output.append(f"*Why*: {role['reasoning']}\n")
        
        output.append("#### Key Skills to Emphasize")
        for skill in role.get('key_skills_to_emphasize', []):
            output.append(f"- {skill}")
        output.append("")
        
        output.append("#### Target Companies")
        for company in role.get('suggested_companies', []):
            output.append(f"- {company}")
        output.append("")
        
        output.append("#### Active Opportunities")
        for idx, job in enumerate(role.get('current_opportunities', []), 1):
            output.append(f"{idx}. [{job['title']}]({job['url']})")
            output.append(f"   - Company: {job['company']}")
            output.append(f"   - Status: To Apply")
            if job.get('notes'):
                output.append(f"   - Notes: {job['notes']}")
            output.append("")
    
    # Networking Strategy
    output.append("## Networking Strategy")
    network = strategy.get('networking_strategy', {})
    output.append(f"**Daily Connection Target**: {network.get('daily_connections', 3)}\n")
    
    output.append("### Platforms")
    for platform in network.get('platforms', []):
        output.append(f"- {platform}")
    output.append("")
    
    output.append("### Outreach Template")
    output.append("```")
    output.append(network.get('message_template', ''))
    output.append("```\n")
    
    output.append("### Target Connections")
    for target in network.get('target_individuals', []):
        output.append(f"- {target}")
    output.append("")
    
    # Skill Development
    output.append("## Skill Development Plan\n")
    for skill in strategy.get('skill_development', []):
        output.append(f"### Current Focus: {skill['skill']}")
        output.append(f"- **Goal**: {skill['action']}")
        output.append(f"- **Timeline**: {skill['timeline']}")
        if skill.get('status'):
            output.append(f"- **Status**: {skill['status']}")
        output.append("")
    
    # Application Strategy
    app_strategy = strategy.get('application_strategy', {})
    output.append("## Application Strategy")
    output.append(f"**Daily Target**: {app_strategy.get('daily_target', 1)} high-quality application\n")
    
    output.append("### Quality Checklist")
    for item in app_strategy.get('quality_checklist', []):
        output.append(f"- [ ] {item}")
    output.append("")
    
    output.append("### Customization Points")
    for point in app_strategy.get('customization_points', []):
        output.append(f"- {point}")
    output.append("")
    
    output.append("### Tracking")
    output.append(app_strategy.get('tracking_method', ''))
    
    return "\n".join(output)

def main():
    logger.info("Starting job strategy generation process")
    
    # Add the parent directory to Python path to find local modules
    import sys
    from pathlib import Path
    root_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root_dir))
    
    
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate job search strategy')
    parser.add_argument('--job-limit', type=int, default=5,
                      help='Number of job postings to return per search query (default: 5)')
    args = parser.parse_args()
    
    try:
        experiences, skills = get_profile_data()
        search_queries = [
            "Cloud Architect",
            "Principal Cloud Engineer",
            "DevOps Architect"
        ]
        
        job_searches = []
        for query in search_queries:
            jobs = search_linkedin_jobs(query, limit=args.job_limit)
            if jobs:
                job_searches.append({
                    "role": query,
                    "listings": jobs
                })
            time.sleep(random.uniform(1, 2))
        
        # Generate tailored documents for high-priority jobs
        generated_docs = generate_documents_for_jobs(job_searches)
        
        strategy = generate_daily_strategy(experiences, skills, job_limit=args.job_limit)
        if strategy:
            strategy['generated_documents'] = generated_docs
            
        weekly_focus = generate_weekly_focus()
        
        # Format the output in both Markdown and plain text
        markdown_content = format_strategy_output(strategy, weekly_focus)
        plain_content = format_strategy_output_plain(strategy, weekly_focus)
        
        # Generate filenames with current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        base_filename = f"strategy_{current_date}"
        
        # Save Markdown version
        STRATEGY_DIR = os.path.join(root_dir, 'strategies')
        md_path = os.path.join(STRATEGY_DIR, f"{base_filename}.md")
        with open(md_path, 'w') as f:
            f.write(markdown_content)
        
        # Save plain text version for backwards compatibility
        txt_path = os.path.join(STRATEGY_DIR, f"{base_filename}.txt")
        with open(txt_path, 'w') as f:
            f.write(plain_content)
        
        logger.info(f"Strategy saved to {md_path} and {txt_path}")
        
        return strategy
    except Exception as e:
        logger.error(f"Failed to generate job strategy: {str(e)}")
        raise  # Re-raise the exception to see the full traceback

if __name__ == "__main__":
    main()