import os
import json
from pathlib import Path
from datetime import datetime
from models import Experience, Skill, TargetRole
from utils import session_scope
from logging_utils import setup_logging
import google.generativeai as genai
from dotenv import load_dotenv

# Configure Google Generative AI
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

logger = setup_logging('strategy_generator')

def get_profile_data():
    """Get profile data from the database"""
    logger.info("Retrieving profile data from database")
    try:
        with session_scope() as session:
            experiences = session.query(Experience).order_by(Experience.end_date.desc()).all()
            skills = session.query(Skill).all()
            roles = session.query(TargetRole).all()
            
            profile_data = {
                'experiences': [
                    {
                        'title': exp.title,
                        'company': exp.company,
                        'start_date': exp.start_date,
                        'end_date': exp.end_date,
                        'description': exp.description
                    } for exp in experiences
                ],
                'skills': [
                    {
                        'skill_name': getattr(skill, 'skill_name', 'Unknown'),
                        'years': getattr(skill, 'years', 0),
                        'proficiency': getattr(skill, 'proficiency', 'Beginner')
                    } for skill in skills
                ],
                'target_roles': [
                    {
                        'title': getattr(role, 'role_name', 'Unknown'),
                        'industry': getattr(role, 'industry', 'Tech'),
                        'salary_range': getattr(role, 'salary_range', ''),
                        'priority': getattr(role, 'priority', 1)
                    } for role in roles
                ]
            }
            
            logger.info("Successfully retrieved profile data")
            return profile_data
    except Exception as e:
        logger.error(f"Error retrieving profile data: {str(e)}")
        return {'experiences': [], 'skills': [], 'target_roles': []}

def generate_daily_strategy(sorted_jobs):
    """Generate a daily strategy based on the analyzed jobs"""
    logger.info("Generating daily strategy")
    
    # Get profile data
    profile_data = get_profile_data()
    
    # Construct the prompt for Gemini
    job_list = ""
    for i, job in enumerate(sorted_jobs[:10], 1):  # Limit to top 10 jobs
        job_list += f"Job {i}: {job['title']} at {job['company']}\n"
        job_list += f"   Match Score: {job.get('match_score', 0)}\n"  # Use get() with default value
        job_list += f"   Application Priority: {job.get('application_priority', 'Medium')}\n"  # Use get() with default
        job_list += f"   Key Requirements: {', '.join(job.get('key_requirements', ['Not specified']))}\n"  # Use get() with default
        job_list += f"   Career Growth Potential: {job.get('career_growth_potential', 'Unknown')}\n\n"  # Use get() with default
    
    # Fix skill_name attribute reference
    skills_list = ", ".join([f"{skill.get('skill_name', skill.get('name', 'Unknown'))} ({skill.get('proficiency', 'N/A')})" for skill in profile_data['skills']])
    target_roles_list = ", ".join([role['title'] for role in profile_data['target_roles']])
    
    prompt = f"""You are a career strategist helping to create a daily job search strategy. Based on today's job matches, create a compelling strategy document with the following sections:

1. Today's Focus: A concise strategy for today's job search approach
2. High-Priority Applications: List 1-3 jobs that should be applied to today with a brief reason for each
3. Skill Alignment: Identify skills from the candidate's profile that align well with today's job matches
4. Areas for Improvement: Suggest 1-2 skill areas to develop based on gaps in job requirements
5. Weekly Focus Update: Suggest adjustments to the weekly focus based on today's job trends

Candidate Skills: {skills_list}
Target Roles: {target_roles_list}

Today's Top Job Matches:
{job_list}

Today's date: {datetime.now().strftime('%Y-%m-%d')}

Format your response as detailed paragraphs for each section. Be specific and actionable."""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.7,
            }
        )
        
        strategy = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'content': response.text,
            'jobs': sorted_jobs[:10]  # Include top 10 jobs in the strategy
        }
        
        logger.info("Successfully generated daily strategy")
        return strategy
    except Exception as e:
        logger.error(f"Error generating daily strategy: {str(e)}")
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'content': "Unable to generate strategy due to an error.",
            'jobs': sorted_jobs[:10]
        }

def generate_weekly_focus(strategies_of_week):
    """Generate a weekly focus based on the daily strategies of the past week"""
    logger.info("Generating weekly focus")
    
    if not strategies_of_week:
        logger.warning("No daily strategies provided for weekly focus generation")
        return "No data available to generate weekly focus."
    
    # Compile job data from all strategies
    all_jobs = []
    for strategy in strategies_of_week:
        all_jobs.extend(strategy.get('jobs', []))
    
    # Count job titles and companies
    job_titles = {}
    companies = {}
    skills_required = {}
    
    for job in all_jobs:
        # Count job titles
        title = job.get('title', '').lower()
        job_titles[title] = job_titles.get(title, 0) + 1
        
        # Count companies
        company = job.get('company', '').lower()
        companies[company] = companies.get(company, 0) + 1
        
        # Count required skills
        for req in job.get('key_requirements', []):
            req_lower = req.lower()
            skills_required[req_lower] = skills_required.get(req_lower, 0) + 1
    
    # Sort by frequency
    top_titles = sorted(job_titles.items(), key=lambda x: x[1], reverse=True)[:5]
    top_companies = sorted(companies.items(), key=lambda x: x[1], reverse=True)[:5]
    top_skills = sorted(skills_required.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Create prompt for Gemini
    titles_text = "\n".join([f"- {title}: {count} occurrences" for title, count in top_titles])
    companies_text = "\n".join([f"- {company}: {count} occurrences" for company, count in top_companies])
    skills_text = "\n".join([f"- {skill}: {count} occurrences" for skill, count in top_skills])
    
    prompt = f"""As a career strategist, analyze the past week's job market data and create a weekly focus strategy with these sections:

1. Market Trends: Analyze patterns in job titles and companies
2. In-Demand Skills: Identify the most sought-after skills this week
3. Weekly Focus: Recommend a focused approach for next week's job search
4. Skill Development: Suggest 2-3 skills to prioritize developing
5. Application Strategy: Recommend which types of roles to prioritize

Past Week's Data:

Most Common Job Titles:
{titles_text}

Most Common Companies:
{companies_text}

Most Requested Skills:
{skills_text}

Format your response as detailed paragraphs for each section. Be specific and actionable."""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.7,
            }
        )
        
        logger.info("Successfully generated weekly focus")
        return response.text
    except Exception as e:
        logger.error(f"Error generating weekly focus: {str(e)}")
        return "Unable to generate weekly focus due to an error."

def format_strategy_output(strategy, include_weekly_focus=True):
    """Format strategy output in markdown format"""
    logger.info("Formatting strategy output in markdown")
    
    content = strategy.get('content', '')
    date = strategy.get('date', datetime.now().strftime('%Y-%m-%d'))
    jobs = strategy.get('jobs', [])
    weekly_focus = strategy.get('weekly_focus', '')
    
    output = []
    output.append(f"# Job Search Strategy - {date}\n")
    output.append(content)
    output.append("\n## Today's Top Job Matches\n")
    
    # Add job information
    for i, job in enumerate(jobs, 1):
        title = job.get('title', 'Unknown Position')
        company = job.get('company', 'Unknown Company')
        priority = job.get('application_priority', 'Low')
        score = job.get('match_score', 0)
        requirements = ', '.join(job.get('key_requirements', ['None specified']))
        growth = job.get('career_growth_potential', 'Unknown')
        url = job.get('url', '#')
        
        output.append(f"### {i}. {title} at {company}\n")
        output.append(f"**Priority**: {priority.upper()} | **Match Score**: {score}%\n")
        output.append(f"**Key Requirements**: {requirements}\n")
        output.append(f"**Career Growth**: {growth}\n")
        if url != '#':
            output.append(f"[View Job]({url})\n")
    
    # Add weekly focus if available
    if include_weekly_focus and weekly_focus:
        output.append("\n## Weekly Focus\n")
        output.append(weekly_focus)
    
    # Add recruiters if available
    if 'recruiters' in strategy and strategy['recruiters']:
        output.append("\n## Company Recruiters\n")
        output.append("Connect with these recruiters to expand your network and get insider information on job openings.\n")
        
        for company, recruiters in strategy['recruiters'].items():
            output.append(f"### {company}\n")
            for recruiter in recruiters:
                name = recruiter.get('name', 'Unknown')
                title = recruiter.get('title', 'Unknown')
                url = recruiter.get('url', '')
                
                if url:
                    output.append(f"- [{name}]({url}) - {title}")
                else:
                    output.append(f"- **{name}** - {title}")
                    
                if 'status' in recruiter:
                    output.append(f"  - Status: {recruiter['status']}")
            output.append("")
    
    return '\n'.join(output)

def format_strategy_output_plain(strategy, include_weekly_focus=True):
    """Format strategy output in plain text format"""
    logger.info("Formatting strategy output in plain text")
    
    content = strategy.get('content', '')
    date = strategy.get('date', datetime.now().strftime('%Y-%m-%d'))
    jobs = strategy.get('jobs', [])
    weekly_focus = strategy.get('weekly_focus', '')
    
    output = []
    output.append(f"JOB SEARCH STRATEGY - {date}")
    output.append('=' * 80)
    output.append('')
    output.append(content)
    output.append('')
    output.append("TODAY'S TOP JOB MATCHES")
    output.append('=' * 80)
    
    # Add job information
    for i, job in enumerate(jobs, 1):
        output.append(f"\nJOB {i}: {job.get('title', 'Unknown Position')} at {job.get('company', 'Unknown Company')}")
        output.append(f"Priority: {job.get('application_priority', 'Low').upper()}  |  Match Score: {job.get('match_score', 0)}%")
        output.append(f"Key Requirements: {', '.join(job.get('key_requirements', ['None specified']))}")
        output.append(f"Career Growth: {job.get('career_growth_potential', 'Unknown')}")
        output.append('-' * 50)
    
    # Add weekly focus if available
    if include_weekly_focus and weekly_focus:
        output.append("\nWEEKLY FOCUS")
        output.append('=' * 80)
        output.append(weekly_focus)
    
    # Add recruiters if available
    if 'recruiters' in strategy and strategy['recruiters']:
        output.append("\nRECRUITERS FOUND")
        output.append('=' * 80)
        for company, recruiters in strategy['recruiters'].items():
            output.append(f"\n{company}:")
            for recruiter in recruiters:
                output.append(f"- {recruiter.get('name', 'Unknown')}, {recruiter.get('title', 'Unknown')}")
                if 'url' in recruiter:
                    output.append(f"  URL: {recruiter['url']}")
    
    return '\n'.join(output)