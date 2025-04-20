#!/usr/bin/env python3
import os
import json
import sys
import random
import time
import argparse
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

def generate_and_save_strategy(job_searches, output_dir, send_slack=DEFAULT_SLACK_NOTIFICATIONS, include_recruiters=False):
    """Generate and save job search strategy"""
    logger.info("Generating job search strategy")
    
    # Flatten job list
    all_jobs = []
    for search in job_searches:
        all_jobs.extend(search["listings"])
    
    # Find recruiters if requested
    recruiters = {}
    if include_recruiters:
        recruiters = find_recruiters_for_jobs(job_searches)
    
    # Generate strategy
    strategy = generate_daily_strategy(all_jobs)
    
    # For weekly focus, we should ideally have past strategies
    # Since we don't have them readily available, we'll pass an empty list for now
    # This will result in a generic weekly focus message
    weekly_focus = generate_weekly_focus([])  # Pass empty list instead of no arguments
    
    # Add recruiters and weekly focus to strategy
    if recruiters:
        strategy['recruiters'] = recruiters
    strategy['weekly_focus'] = weekly_focus
    
    # Format the output in both Markdown and plain text
    markdown_content = format_strategy_output(strategy, weekly_focus)
    plain_content = format_strategy_output_plain(strategy, weekly_focus)
    
    # Generate filenames with current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    base_filename = f"strategy_{current_date}"
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Save Markdown version
    md_path = os.path.join(output_dir, f"{base_filename}.md")
    with open(md_path, 'w') as f:
        f.write(markdown_content)
    
    # Save plain text version for backwards compatibility
    txt_path = os.path.join(output_dir, f"{base_filename}.txt")
    with open(txt_path, 'w') as f:
        f.write(plain_content)
    
    logger.info(f"Strategy saved to {md_path} and {txt_path}")
    
    # Send Slack notification if enabled
    if send_slack and SLACK_AVAILABLE:
        try:
            logger.info("Sending Slack notification about generated job strategy")
            
            # Create a summary of the strategy for the notification
            daily_focus = strategy.get('daily_focus', {})
            job_count = len(all_jobs)
            high_priority_count = len([j for j in all_jobs if j.get('application_priority', '').lower() == 'high'])
            recruiter_count = sum(len(recs) for recs in recruiters.values()) if recruiters else 0
            
            # Create a rich formatted message with Slack Block Kit
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
            
            # Add recruiter info if available
            if recruiter_count > 0:
                blocks[2]["fields"].append({
                    "type": "mrkdwn",
                    "text": f"*Recruiters Found:* {recruiter_count}"
                })
            
            # Add success metrics if available
            if daily_focus.get('success_metrics'):
                metrics_text = "\n".join([f"• {metric}" for metric in daily_focus.get('success_metrics', [])])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Success Metrics:*\n{metrics_text}"
                    }
                })
            
            # Add a link to the strategy file
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<https://github.com/darnold/jobsearch/blob/main/strategies/{os.path.basename(md_path)}|View full strategy>"
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
            
    return strategy, md_path, txt_path

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
    parser.set_defaults(send_slack=DEFAULT_SLACK_NOTIFICATIONS)
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
            search_queries = [
                "Cloud Architect",
                "Principal Cloud Engineer", 
                "DevOps Architect"
            ]
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
                args.include_recruiters
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