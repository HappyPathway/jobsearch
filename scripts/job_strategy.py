#!/usr/bin/env python3
import os
import json
import sys
import random
import time
import argparse
import tempfile
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
import google.generativeai as genai

# Local module imports
from logging_utils import setup_logging
from job_search import search_linkedin_jobs
from document_generator import generate_documents_for_jobs
from strategy_generator import generate_daily_strategy, generate_weekly_focus
from strategy_formatter import format_strategy_output, format_strategy_output_plain
from recruiter_finder import get_recruiter_finder
from gcs_utils import gcs

# Import Slack notifier
try:
    from slack_notifier import get_notifier
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

logger = setup_logging('job_strategy')

# Check if Slack notifications are enabled by default
DEFAULT_SLACK_NOTIFICATIONS = os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false").lower() in ["true", "1", "yes"]

def search_jobs(search_queries, job_limit=5):
    """Search for jobs across multiple queries and return results"""
    logger.info(f"Searching for jobs with queries: {search_queries}")
    
    job_searches = []
    for query in search_queries:
        jobs = search_linkedin_jobs(query, limit=job_limit)
        if jobs:
            job_searches.append({
                "role": query,
                "listings": jobs
            })
        time.sleep(random.uniform(1, 2))  # Pause between queries
    
    logger.info(f"Found {sum(len(search['listings']) for search in job_searches)} jobs across {len(job_searches)} search queries")
    return job_searches

def find_recruiters_for_jobs(job_searches, limit_per_company=2, cache_only=True):
    """Find recruiters for companies with job listings"""
    logger.info("Searching for recruiters at companies with job listings")
    
    # Get recruiter finder instance
    recruiter_finder = get_recruiter_finder()
    
    # Track companies we've already processed to avoid duplicates
    processed_companies = set()
    
    # Dictionary to store recruiters by company
    company_recruiters = {}
    
    # Process each job search result
    for search in job_searches:
        for job in search["listings"]:
            company = job.get("company")
            if not company or company in processed_companies:
                continue
                
            processed_companies.add(company)
            
            # Find recruiters for this company
            recruiters = recruiter_finder.search_company_recruiters(
                company, 
                limit=limit_per_company, 
                cache_only=cache_only
            )
            
            if recruiters:
                company_recruiters[company] = recruiters
                logger.info(f"Found {len(recruiters)} recruiters for {company}")
    
    logger.info(f"Found recruiters for {len(company_recruiters)} companies")
    return company_recruiters

def validate_strategy_content(strategy):
    """Validate the content of the strategy"""
    return bool(strategy.get('daily_focus')) and bool(strategy.get('weekly_focus'))

def enhance_with_default_content(strategy):
    """Enhance strategy with default content"""
    strategy['daily_focus'] = strategy.get('daily_focus', {'title': 'Default Daily Focus'})
    strategy['weekly_focus'] = strategy.get('weekly_focus', 'Default Weekly Focus')
    return strategy

def get_sample_jobs():
    """Provide sample job data for fallback"""
    return [
        {"title": "Sample Job 1", "company": "Sample Company A", "application_priority": "high"},
        {"title": "Sample Job 2", "company": "Sample Company B", "application_priority": "medium"},
        {"title": "Sample Job 3", "company": "Sample Company C", "application_priority": "low"}
    ]

def get_target_roles_from_profile():
    """Extract target job roles from the user's profile data in the database"""
    logger.info("Retrieving target roles from profile data")
    try:
        # Import needed modules
        from models import TargetRole, Experience
        from utils import session_scope
        from strategy_generator import get_profile_data
        
        # First try to get from database
        try:
            with session_scope() as session:
                roles = session.query(TargetRole).all()
                if roles:
                    target_roles = [role.role_name for role in roles if hasattr(role, 'role_name') and role.role_name]
                    logger.info(f"Found {len(target_roles)} target roles in database: {target_roles}")
                    return target_roles
        except Exception as e:
            logger.warning(f"Error accessing database for target roles: {str(e)}")
        
        # If database query fails, try using profile data from strategy generator
        profile_data = get_profile_data()
        if profile_data and 'target_roles' in profile_data and profile_data['target_roles']:
            target_roles = [role['title'] for role in profile_data['target_roles'] if 'title' in role and role['title']]
            if target_roles:
                logger.info(f"Found {len(target_roles)} target roles from profile data: {target_roles}")
                return target_roles
                
        # Try to get previous job titles from user's experience (NEW FALLBACK)
        previous_titles = []
        
        # First try from database
        try:
            with session_scope() as session:
                experiences = session.query(Experience).order_by(Experience.end_date.desc()).all()
                if experiences:
                    previous_titles = [exp.title for exp in experiences if hasattr(exp, 'title') and exp.title]
                    logger.info(f"Found {len(previous_titles)} previous job titles in database: {previous_titles}")
        except Exception as e:
            logger.warning(f"Error accessing database for experience: {str(e)}")
            
        # If database query fails, try using profile data
        if not previous_titles and profile_data and 'experiences' in profile_data:
            previous_titles = [exp.get('title') for exp in profile_data['experiences'] if 'title' in exp and exp['title']]
            logger.info(f"Found {len(previous_titles)} previous job titles from profile data: {previous_titles}")
        
        # If we have previous titles, use them
        if previous_titles:
            # Limit to 3-5 most recent titles and remove duplicates while preserving order
            seen = set()
            unique_titles = []
            for title in previous_titles:
                if title not in seen:
                    seen.add(title)
                    unique_titles.append(title)
            
            return unique_titles[:5]
        
        # If no roles are found in profile data, analyze skills to suggest roles
        if profile_data and 'skills' in profile_data and profile_data['skills']:
            skill_names = [skill['skill_name'] for skill in profile_data['skills'] if 'skill_name' in skill]
            top_skills = skill_names[:5] if len(skill_names) > 5 else skill_names
            
            if top_skills:
                logger.info(f"No target roles found, attempting to analyze skills: {top_skills}")
                target_roles = suggest_roles_from_skills(top_skills)
                if target_roles:
                    return target_roles
    
    except Exception as e:
        logger.error(f"Error getting target roles from profile: {str(e)}")
    
    # Default fallback roles if nothing else works
    fallback_roles = ["Software Engineer", "Project Manager", "Data Analyst"]
    logger.warning(f"Using generic fallback target roles: {fallback_roles}")
    return fallback_roles

def suggest_roles_from_skills(skills):
    """Use AI to suggest job roles based on user's top skills"""
    logger.info(f"Suggesting job roles based on skills: {skills}")
    
    try:
        skills_text = ", ".join(skills)
        
        prompt = f"""Based on the following professional skills, suggest 3-5 specific job titles/roles that would be a good match for a job search:

Skills: {skills_text}

Provide only the job titles as a comma-separated list. Be specific and relevant to the listed skills."""
        
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 100,
                "temperature": 0.2,
            }
        )
        
        # Process the response to extract role names
        if response and response.text:
            # Split by common separators and clean up
            suggested_roles = [role.strip() for role in response.text.replace('\n', ',').split(',')]
            # Filter out empty strings
            suggested_roles = [role for role in suggested_roles if role]
            
            if suggested_roles:
                logger.info(f"AI suggested roles: {suggested_roles}")
                return suggested_roles[:5]  # Limit to 5 roles
    
    except Exception as e:
        logger.error(f"Error suggesting roles from skills: {str(e)}")
    
    return None

def generate_and_save_strategy(job_searches, output_dir, send_slack=DEFAULT_SLACK_NOTIFICATIONS, include_recruiters=False, cache_only=True):
    """Generate and save job search strategy"""
    logger.info("Generating job search strategy")
    
    # Flatten job list
    all_jobs = []
    for search in job_searches:
        all_jobs.extend(search["listings"])
    
    # Validate that we have enough job data to generate a meaningful strategy
    if not all_jobs or len(all_jobs) < 3:
        logger.warning("Insufficient job data to generate a meaningful strategy (fewer than 3 jobs)")
        # Create fallback job data during initialization to ensure we have content
        if not all_jobs:
            logger.info("Using sample job data for strategy generation")
            all_jobs = get_sample_jobs()
    
    # Find recruiters if requested
    recruiters = {}
    if include_recruiters:
        recruiters = find_recruiters_for_jobs(job_searches, cache_only=cache_only)
    
    # Generate strategy
    strategy = generate_daily_strategy(all_jobs)
    
    # Add recruiters and weekly focus to strategy
    if recruiters:
        strategy['recruiters'] = recruiters
    strategy['weekly_focus'] = generate_weekly_focus([])
    
    # Validate strategy content
    if not validate_strategy_content(strategy):
        logger.warning("Generated strategy content is incomplete, enhancing with default content")
        strategy = enhance_with_default_content(strategy)
    
    # Generate filenames with current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    base_filename = f"strategy_{current_date}"
    
    # Store in GCS
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_md:
        temp_md_path = Path(temp_md.name)
        temp_md.write(format_strategy_output(strategy, strategy['weekly_focus']))
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_txt:
        temp_txt_path = Path(temp_txt.name)
        temp_txt.write(format_strategy_output_plain(strategy, strategy['weekly_focus']))

    # Upload to GCS
    md_gcs_path = f'strategies/{base_filename}.md'
    txt_gcs_path = f'strategies/{base_filename}.txt'

    gcs.upload_file(temp_md_path, md_gcs_path)
    gcs.upload_file(temp_txt_path, txt_gcs_path)

    # Clean up temp files
    temp_md_path.unlink()
    temp_txt_path.unlink()
    
    logger.info(f"Strategy saved to GCS at {md_gcs_path} and {txt_gcs_path}")
    
    # Send Slack notification if enabled
    if send_slack and SLACK_AVAILABLE and validate_strategy_content(strategy):
        try:
            logger.info("Sending Slack notification about generated job strategy")
            daily_focus = strategy.get('daily_focus', {})
            job_count = len(all_jobs)
            high_priority_count = len([j for j in all_jobs if j.get('application_priority', '').lower() == 'high'])
            recruiter_count = sum(len(recs) for recs in recruiters.values()) if recruiters else 0
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🎯 Job Search Strategy for {current_date}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Today's Focus:* {daily_focus.get('title', 'Daily Planning')}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*New Job Opportunities:* {job_count}"
                        },
                        {
                            "type": "mrkdwn", 
                            "text": f"*High-Priority Applications:* {high_priority_count}"
                        }
                    ]
                }
            ]
            
            # Add success metrics section using formatted metrics
            if daily_focus.get('formatted_metrics'):
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Success Metrics",
                        "emoji": True
                    }
                })
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": daily_focus['formatted_metrics']
                    }
                })
            
            # Add high priority job details
            high_priority_jobs = [j for j in all_jobs if j.get('application_priority', '').lower() == 'high']
            if high_priority_jobs:
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🔥 High Priority Opportunities",
                        "emoji": True
                    }
                })
                
                for job in high_priority_jobs[:5]:  # Limit to top 5
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*<{job['url']}|{job['title']}>*\n"
                                f"*Company:* {job['company']}\n"
                                f"*Match Score:* {job.get('match_score', 0)}%\n"
                                f"*Requirements:* {', '.join(job.get('key_requirements', ['None specified']))}"
                            )
                        }
                    })
            
            # Add a link to the strategy file
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{md_gcs_path}|📝 View full strategy>"
                }
            })
            
            # Send the notification
            notifier = get_notifier()
            notifier.send_notification(
                f"Job Search Strategy for {current_date} has been generated",
                blocks=blocks
            )
            logger.info("Slack notification sent successfully")
        except Exception as e:
            logger.error(f"Error sending Slack notification: {str(e)}")
    
    return strategy, md_gcs_path, txt_gcs_path

def generate_medium_article(strategy, preview_only=False):
    """Generate a Medium article based on skills in the strategy"""
    try:
        logger.info("Generating Medium article based on job strategy skills")
        
        # Import the Medium publisher
        from medium_publisher import MediumPublisher
        
        # Initialize Medium publisher
        publisher = MediumPublisher()
        
        # Generate article in appropriate mode
        if preview_only:
            logger.info("Running Medium article generation in preview mode")
            selected_skill = publisher.select_skill_for_article()
            if selected_skill:
                article_data = publisher.generate_article(selected_skill)
                if article_data:
                    article_path = publisher.save_article_locally(article_data)
                    logger.info(f"Generated article preview: {article_path}")
                    return article_path
        else:
            logger.info("Running Medium article generation and publication")
            result = publisher.generate_and_publish_article()
            logger.info(f"Article generation complete: {result}")
            return result
    except Exception as e:
        logger.error(f"Error generating Medium article: {str(e)}")
        return None

def main():
    """Main entry point for job strategy generation"""
    logger.info("Starting job strategy generation process")
    
    # Add the parent directory to Python path to find local modules
    root_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root_dir))
    
    # Load environment variables
    load_dotenv()
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Generate job search strategy')
    parser.add_argument('--job-limit', type=int, default=5,
                      help='Number of job postings to return per search query (default: 5)')
    parser.add_argument('--search-only', action='store_true',
                      help='Only search for jobs, do not generate strategy')
    parser.add_argument('--strategy-only', action='store_true',
                      help='Only generate strategy from existing job data')
    parser.add_argument('--job-file', type=str,
                      help='Path to JSON file with job data when using --strategy-only')
    parser.add_argument('--no-slack', action='store_false', dest='send_slack',
                      help='Disable Slack notifications')
    parser.add_argument('--generate-article', action='store_true',
                      help='Generate a Medium article based on skills in the strategy')
    parser.add_argument('--preview-article', action='store_true',
                      help='Generate a Medium article in preview mode (no publishing)')
    parser.add_argument('--generate-documents', action='store_true',
                      help='Generate documents for high-priority jobs')
    parser.add_argument('--include-recruiters', action='store_true',
                      help='Include recruiter search in strategy generation')
    parser.add_argument('--cache-only', action='store_true',
                      help='Only use cached recruiters, do not search online')
    parser.add_argument('--no-cache-only', action='store_false', dest='cache_only',
                      help='Allow searching for recruiters online')
    parser.set_defaults(send_slack=DEFAULT_SLACK_NOTIFICATIONS, cache_only=True)
    args = parser.parse_args()
    
    try:
        job_searches = []
        strategy = None
        
        # Determine operation mode based on arguments
        if args.search_only and args.strategy_only:
            logger.error("Cannot specify both --search-only and --strategy-only")
            return 1
        
        # Search for jobs if not in strategy-only mode
        if not args.strategy_only:
            # Get target roles dynamically from user's profile instead of hardcoded values
            search_queries = get_target_roles_from_profile()
            
            # Ensure we have at least 2-3 search queries for better results
            if len(search_queries) < 2:
                logger.warning(f"Only found {len(search_queries)} target roles, adding fallback roles")
                additional_roles = ["Software Engineer", "Project Manager", "Data Analyst"]
                for role in additional_roles:
                    if role not in search_queries:
                        search_queries.append(role)
                        if len(search_queries) >= 3:
                            break
            
            logger.info(f"Using search queries from profile data: {search_queries}")
            job_searches = search_jobs(search_queries, args.job_limit)
            
            # Save job data for potential future use
            job_data_path = os.path.join(root_dir, 'job_data.json')
            with open(job_data_path, 'w') as f:
                json.dump(job_searches, f, indent=2)
            logger.info(f"Job search data saved to {job_data_path}")
            
            # Exit if search-only mode
            if args.search_only:
                logger.info("Job search completed. Exiting as requested (--search-only).")
                return 0
        
        # Load job data from file if in strategy-only mode
        elif args.strategy_only:
            if args.job_file:
                job_file = args.job_file
            else:
                job_file = os.path.join(root_dir, 'job_data.json')
                
            if not os.path.exists(job_file):
                logger.error(f"Job data file not found: {job_file}")
                return 1
                
            with open(job_file, 'r') as f:
                job_searches = json.load(f)
            logger.info(f"Loaded job data from {job_file}")
        
        # Generate strategy if not in search-only mode
        if not args.search_only:
            strategy_dir = os.path.join(root_dir, 'strategies')
            strategy, md_path, txt_path = generate_and_save_strategy(
                job_searches, 
                strategy_dir,
                args.send_slack,
                args.include_recruiters,
                args.cache_only
            )
        
        # Generate documents if requested
        if args.generate_documents and job_searches:
            logger.info("Generating documents for high-priority jobs")
            generated_docs = generate_documents_for_jobs(job_searches, filter_priority="high")
            logger.info(f"Generated {len(generated_docs)} document sets for high-priority jobs")
        
        # Generate Medium article if requested
        if (args.generate_article or args.preview_article) and strategy:
            article_result = generate_medium_article(
                strategy, 
                preview_only=args.preview_article
            )
            if article_result:
                logger.info(f"Medium article generation successful: {article_result}")
            
        logger.info("Job strategy generation process completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Failed to generate job strategy: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())