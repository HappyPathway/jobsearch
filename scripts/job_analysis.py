import os
import json
import re
from dotenv import load_dotenv
import google.generativeai as genai
from logging_utils import setup_logging

logger = setup_logging('job_analysis')

# Configure Google Generative AI
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

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

    # Get candidate profile data from the database
    try:
        from utils import session_scope
        from models import Experience, Skill, TargetRole
        
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
        
        # Instead of extracting skills directly from the job description (which would be circular),
        # we'll ask Gemini to evaluate the job directly in the fallback case
        logger.info("Using direct job evaluation approach since profile data is unavailable")
        
        job_title = job_info.get('title', '')
        job_company = job_info.get('company', '')
        job_description = job_info.get('description', '')
        
        # Set minimal placeholder values that won't affect evaluation
        skill_list = ["Technical Professional"]
        target_roles = ["Technical Role"]
        experience_summary = "Professional with relevant experience"

    # Create a formatted skills section, grouping if possible
    skill_text = ""
    if len(skill_list) > 15:
        # If we have many skills, just list top ones
        skill_text = "- " + "\n- ".join(skill_list[:15])
    else:
        skill_text = "- " + "\n- ".join(skill_list)
    
    # Build dynamic prompt with candidate data
    prompt = f"""You are a job analysis expert. Analyze this job posting and evaluate how well it matches the candidate's profile. Return ONLY a valid JSON object with no additional text or formatting.

Job Details:
Title: {job_info['title']}
Company: {job_info['company']}
Description: {job_info['description']}

Candidate Profile:
Target Roles: {', '.join(target_roles)}
Recent Experience:
{experience_summary}

Candidate Skills:
{skill_text}

Analyze this job based on the following criteria:
1. Match Score: Rate 0-100 how well the candidate's skills and experience match this job
2. Key Requirements: Identify the top 3-5 technical requirements from the job description  
3. Culture Indicators: Find signals of company culture/work environment
4. Career Growth: Assess potential for career advancement
5. Application Priority: Determine if this is a high/medium/low priority application based on match and growth potential

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