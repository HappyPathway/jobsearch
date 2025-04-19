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
                        'name': skill.name,
                        'years': skill.years,
                        'proficiency': skill.proficiency
                    } for skill in skills
                ],
                'target_roles': [
                    {
                        'title': role.title,
                        'industry': role.industry,
                        'salary_range': role.salary_range,
                        'priority': role.priority
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
        job_list += f"   Match Score: {job['match_score']}\n"
        job_list += f"   Application Priority: {job['application_priority']}\n"
        job_list += f"   Key Requirements: {', '.join(job['key_requirements'])}\n"
        job_list += f"   Career Growth Potential: {job['career_growth_potential']}\n\n"
    
    skills_list = ", ".join([f"{skill['name']} ({skill['proficiency']})" for skill in profile_data['skills']])
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
    """Format strategy output in HTML format"""
    logger.info("Formatting strategy output in HTML")
    
    content = strategy['content']
    date = strategy['date']
    jobs = strategy.get('jobs', [])
    weekly_focus = strategy.get('weekly_focus', '')
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Search Strategy - {date}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        h1 {{
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            margin-top: 30px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }}
        .job-card {{
            background-color: #f9f9f9;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 4px;
        }}
        .job-title {{
            font-weight: bold;
            color: #2980b9;
        }}
        .job-company {{
            font-style: italic;
        }}
        .job-priority {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .high {{
            background-color: #e74c3c;
            color: white;
        }}
        .medium {{
            background-color: #f39c12;
            color: white;
        }}
        .low {{
            background-color: #2ecc71;
            color: white;
        }}
        .score {{
            display: inline-block;
            padding: 3px 8px;
            background-color: #34495e;
            color: white;
            border-radius: 3px;
            font-size: 0.8em;
        }}
        .weekly-focus {{
            background-color: #f1f8ff;
            border-left: 4px solid #2980b9;
            padding: 15px;
            margin-top: 30px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <h1>Job Search Strategy - {date}</h1>
    
    <div class="strategy-content">
        {content.replace('\n', '<br>')}
    </div>
    
    <h2>Today's Top Job Matches</h2>
    """
    
    # Add job cards
    for job in jobs:
        priority_class = job.get('application_priority', 'low').lower()
        score = job.get('match_score', 0)
        
        html += f"""
    <div class="job-card">
        <div class="job-title">{job.get('title', 'Unknown Position')}</div>
        <div class="job-company">{job.get('company', 'Unknown Company')}</div>
        <div>
            <span class="job-priority {priority_class}">{job.get('application_priority', 'Low').upper()}</span>
            <span class="score">Match: {score}%</span>
        </div>
        <p><strong>Key Requirements:</strong> {', '.join(job.get('key_requirements', ['None specified']))}</p>
        <p><strong>Career Growth:</strong> {job.get('career_growth_potential', 'Unknown')}</p>
    </div>
        """
    
    # Add weekly focus if available
    if include_weekly_focus and weekly_focus:
        html += f"""
    <div class="weekly-focus">
        <h2>Weekly Focus</h2>
        {weekly_focus.replace('\n', '<br>')}
    </div>
        """
    
    html += """
</body>
</html>
    """
    
    return html

def format_strategy_output_plain(strategy, include_weekly_focus=True):
    """Format strategy output in plain text format"""
    logger.info("Formatting strategy output in plain text")
    
    content = strategy['content']
    date = strategy['date']
    jobs = strategy.get('jobs', [])
    weekly_focus = strategy.get('weekly_focus', '')
    
    text = f"""JOB SEARCH STRATEGY - {date}
{'=' * 80}

{content}

TODAY'S TOP JOB MATCHES
{'=' * 80}
"""
    
    # Add job information
    for i, job in enumerate(jobs, 1):
        text += f"""
JOB {i}: {job.get('title', 'Unknown Position')} at {job.get('company', 'Unknown Company')}
Priority: {job.get('application_priority', 'Low').upper()}  |  Match Score: {job.get('match_score', 0)}%
Key Requirements: {', '.join(job.get('key_requirements', ['None specified']))}
Career Growth: {job.get('career_growth_potential', 'Unknown')}
{'-' * 50}
"""
    
    # Add weekly focus if available
    if include_weekly_focus and weekly_focus:
        text += f"""
WEEKLY FOCUS
{'=' * 80}
{weekly_focus}
"""
    
    return text