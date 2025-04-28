import os
import json
from pathlib import Path
from datetime import datetime
from jobsearch.core.logging_utils import setup_logging
from jobsearch.core.storage import gcs
from jobsearch.core.markdown import MarkdownGenerator

logger = setup_logging('strategy_formatter')
markdown_generator = MarkdownGenerator()

def format_strategy_output_plain(strategy, weekly_focus=None):
    """Format strategy output in plain text format"""
    logger.info("Formatting strategy output in plain text")
    
    content = strategy.get('content', '')
    date = strategy.get('date', datetime.now().strftime('%Y-%m-%d'))
    jobs = strategy.get('jobs', [])
    company_insights = strategy.get('company_insights', {})
    
    output = []
    output.append(f"JOB SEARCH STRATEGY - {date}")
    output.append('=' * 80)
    output.append('')
    output.append(content)
    output.append('')
    output.append("TODAY'S TOP JOB MATCHES")
    output.append('=' * 80)
    
    # Add job information with company insights
    for i, job in enumerate(jobs, 1):
        company = job.get('company', 'Unknown Company')
        output.append(f"\nJOB {i}: {job.get('title', 'Unknown Position')} at {company}")
        output.append(f"Priority: {job.get('application_priority', 'Low').upper()}  |  Match Score: {job.get('match_score', 0)}%")
        output.append(f"Key Requirements: {', '.join(job.get('key_requirements', ['None specified']))}")
        output.append(f"Career Growth: {job.get('career_growth_potential', 'Unknown')}")
        
        # Add company insights if available
        if company in company_insights:
            insight = company_insights[company]
            
            # Add Glassdoor insights
            if insight.get('glassdoor'):
                glassdoor = insight['glassdoor']
                output.append("\nCompany Culture Insights (Glassdoor):")
                output.append(f"- Work-Life Balance: {glassdoor['work_life_balance']}")
                output.append(f"- Management Quality: {glassdoor['management_quality']}")
                if glassdoor['red_flags']:
                    output.append(f"- Potential Concerns: {', '.join(glassdoor['red_flags'])}")
                output.append(f"- Overall Assessment: {glassdoor['recommendation']}")
            
            # Add TechCrunch insights
            if insight.get('techcrunch'):
                techcrunch = insight['techcrunch']
                output.append("\nCompany Market Insights (TechCrunch):")
                output.append(f"- Market Position: {techcrunch['market_position']}")
                output.append(f"- Growth Trajectory: {techcrunch['growth_trajectory']}")
                if techcrunch['key_developments']:
                    output.append(f"- Recent Developments: {', '.join(techcrunch['key_developments'])}")
                output.append(f"- News Sentiment: {techcrunch['news_sentiment']}")
                if techcrunch['recommendation']:
                    output.append(f"- Overall Assessment: {techcrunch['recommendation']}")
        
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
    date = strategy.get('date', datetime.now())
    jobs = strategy.get('jobs', [])
    company_insights = strategy.get('company_insights', {})
    
    return markdown_generator.generate_strategy(
        content=content,
        date=date if isinstance(date, datetime) else datetime.strptime(date, '%Y-%m-%d'),
        jobs=jobs,
        company_insights=company_insights,
        weekly_focus=weekly_focus
    )

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