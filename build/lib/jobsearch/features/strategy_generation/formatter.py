import os
import json
from pathlib import Path
from datetime import datetime
from logging_utils import setup_logging
from gcs_utils import gcs

logger = setup_logging('strategy_formatter')

def format_strategy_output_plain(strategy, weekly_focus=None):
    """Format strategy output in plain text format"""
    logger.info("Formatting strategy output in plain text")
    
    content = strategy.get('content', '')
    date = strategy.get('date', datetime.now().strftime('%Y-%m-%d'))
    jobs = strategy.get('jobs', [])
    
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
    if weekly_focus:
        output.append("\nWEEKLY FOCUS")
        output.append('=' * 80)
        output.append(weekly_focus)
    
    return '\n'.join(output)

def format_strategy_output_markdown(strategy, weekly_focus=None):
    """Format strategy output in markdown format"""
    logger.info("Formatting strategy output in markdown")
    
    content = strategy.get('content', '')
    date = strategy.get('date', datetime.now().strftime('%Y-%m-%d'))
    jobs = strategy.get('jobs', [])
    
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
    if weekly_focus:
        output.append("\n## Weekly Focus\n")
        output.append(weekly_focus)
    
    return '\n'.join(output)

def store_formatted_strategy(strategy, base_filename):
    """Store formatted strategy content in GCS
    
    Args:
        strategy (dict): Strategy content to format and store
        base_filename (str): Base filename without extension
        
    Returns:
        tuple: (markdown_path, text_path) or (None, None) on error
    """
    try:
        # Generate both formats
        markdown_content = format_strategy_output_markdown(strategy, strategy.get('weekly_focus'))
        text_content = format_strategy_output_plain(strategy, strategy.get('weekly_focus'))
        
        # Store in GCS using safe operations
        md_gcs_path = f'strategies/{base_filename}.md'
        txt_gcs_path = f'strategies/{base_filename}.txt'
        
        success_md = gcs.safe_upload(markdown_content, md_gcs_path)
        success_txt = gcs.safe_upload(text_content, txt_gcs_path)
        
        if success_md and success_txt:
            return md_gcs_path, txt_gcs_path
        else:
            logger.error("Failed to upload one or more strategy files to GCS")
            return None, None
            
    except Exception as e:
        logger.error(f"Error storing formatted strategy: {str(e)}")
        return None, None

def get_formatted_strategy(date):
    """Get formatted strategy content from GCS
    
    Args:
        date (str): Date in YYYY-MM-DD format
        
    Returns:
        dict: Strategy content with 'markdown' and 'text' keys, or None if not found
    """
    try:
        md_path = f'strategies/strategy_{date}.md'
        txt_path = f'strategies/strategy_{date}.txt'
        
        md_content = gcs.safe_download(md_path)
        txt_content = gcs.safe_download(txt_path)
        
        if md_content and txt_content:
            return {
                'markdown': md_content,
                'text': txt_content
            }
        else:
            logger.error(f"Could not download strategy files for {date}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting formatted strategy: {str(e)}")
        return None