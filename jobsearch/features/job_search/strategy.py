"""Job search strategy generation and management using core components."""
import os
import sys
import json
import re
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union, Tuple

from jobsearch.core.logging import setup_logging
from jobsearch.core.models import (
    Experience, Skill, TargetRole, JobCache, JobApplication
)
from jobsearch.core.database import get_session
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import AIEngine
from jobsearch.core.markdown import MarkdownGenerator
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.schemas import (
    DailyStrategy,
    ActionItem,
    NetworkingTarget,
    JobAnalysis,
    CompanyInsight,
    RecentActivity,
    FocusArea,
    WeeklyFocus,
    ProfileData
)

# Initialize core components
logger = setup_logging('job_strategy')
storage = GCSManager()
ai_engine = AIEngine(feature_name='job_strategy')
markdown = MarkdownGenerator()
monitoring = setup_monitoring('job_strategy')
from jobsearch.scripts.strategy_generator import (
    generate_daily_strategy, generate_weekly_focus,
    get_recent_applications, get_high_priority_jobs, get_profile_data
)
from jobsearch.features.strategy_generation.formatter import (
    format_strategy_output_markdown as format_strategy_output,
    format_strategy_output_plain
)
from jobsearch.features.job_search.recruiter import get_recruiter_finder 
from jobsearch.features.common.storage import GCSManager
from jobsearch.core.schemas import (
    DailyStrategy, JobMatch, ActionItem, 
    JobSearchResult, RecruitersByCompany,
    RecruiterInfo
)

# Try to import Slack notifier
try:
    from jobsearch.features.common.slack import get_notifier
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
        # Create and run event loop for each query
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            jobs = loop.run_until_complete(search_jobs_async(query, limit=job_limit))
            if jobs:
                job_searches.append({
                    "role": query,
                    "listings": jobs
                })
        finally:
            loop.close()
        time.sleep(random.uniform(1, 2))  # Pause between queries
    
    logger.info(f"Found {sum(len(search['listings']) for search in job_searches)} jobs across {len(job_searches)} search queries")
    return job_searches

async def search_jobs_async(query: str, location: str = None, limit: int = 5):
    """Async helper function to search jobs"""
    from jobsearch.features.job_search.search import search_jobs as search_jobs_core
    return await search_jobs_core(query, location, limit=limit)

def find_recruiters_for_jobs(job_searches: List[Dict], limit_per_company: int = 2, cache_only: bool = True) -> RecruitersByCompany:
    """Find recruiters for companies with job listings
    
    Args:
        job_searches: List of job search results by role
        limit_per_company: Maximum recruiters to find per company
        cache_only: Whether to only use cached recruiter data
        
    Returns:
        RecruitersByCompany: Mapping of companies to their recruiters
    """
    logger.info("Searching for recruiters at companies with job listings")
    
    # Get recruiter finder instance
    recruiter_finder = get_recruiter_finder()
    
    # Track companies we've already processed to avoid duplicates
    processed_companies = set()
    
    # Dictionary to store validated recruiters by company 
    company_recruiters: Dict[str, List[RecruiterInfo]] = {}
    
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

def validate_strategy_content(strategy: DailyStrategy) -> bool:
    """Validate the content of the strategy
    
    Args:
        strategy: DailyStrategy to validate
        
    Returns:
        bool: Whether the strategy is valid
    """
    if not strategy:
        return False
        
    try:
        _ = DailyStrategy(**strategy.model_dump()) if isinstance(strategy, DailyStrategy) else DailyStrategy(**strategy)
        return True
    except Exception as e:
        logger.warning(f"Strategy validation failed: {e}")
        return False

def create_default_strategy() -> DailyStrategy:
    """Create a default strategy with basic content"""
    return DailyStrategy(
        focus_area="Apply to Priority Jobs",
        goals=[
            "Focus on applying to highest priority roles",
            "Review existing applications",
            "Research target companies"
        ],
        action_items=[
            ActionItem(
                description="Review and apply to high priority job matches",
                priority="high",
                deadline="EOD",
                metrics=["3 applications submitted"]
            ),
            ActionItem(
                description="Research target companies",
                priority="medium",
                deadline="EOD",
                metrics=["3 companies researched"]
            )
        ],
        resources_needed=[
            "Job search platform access",
            "Updated resume",
            "Company research tools"
        ],
        success_metrics={
            "applications": "3 quality applications submitted",
            "research": "3 companies thoroughly researched",
            "networking": "2 meaningful professional connections"
        }
    )

def enhance_with_default_content(strategy: Optional[Union[Dict, DailyStrategy]] = None) -> DailyStrategy:
    """Enhance strategy with default content
    
    Args:
        strategy: Optional existing strategy to enhance
        
    Returns:
        DailyStrategy: Enhanced strategy
    """
    try:
        # If we have a strategy, try to convert/validate it
        if strategy:
            if isinstance(strategy, DailyStrategy):
                return strategy
            return DailyStrategy(**strategy)
    except Exception as e:
        logger.warning(f"Error converting existing strategy, using default: {e}")
    
    # Create default strategy if conversion failed or no strategy provided
    return create_default_strategy()

def get_sample_jobs() -> List[JobMatch]:
    """Provide sample job data for fallback
    
    Returns:
        List[JobMatch]: List of sample job matches
    """
    return [
        JobMatch(
            title="Senior Cloud Engineer",
            company="Sample Tech Co A",
            match_score=95,  # Score from 0-100
            application_priority="high",
            key_requirements=["AWS", "Kubernetes", "Terraform"],
            culture_indicators=["Remote-first", "Strong engineering culture"],
            growth_potential="high"
        ),
        JobMatch(
            title="DevOps Team Lead",
            company="Sample Tech Co B",
            match_score=90,  # Score from 0-100
            application_priority="medium",
            key_requirements=["CI/CD", "Team Leadership", "Cloud Platforms"],
            culture_indicators=["Work-life balance", "Mentorship focus"],
            growth_potential="high"
        ),
        JobMatch(
            title="Platform Engineer",
            company="Sample Tech Co C",
            match_score=75,  # Score from 0-100
            application_priority="medium",
            key_requirements=["Infrastructure as Code", "Cloud Architecture", "Python"],
            culture_indicators=["Startup environment", "Innovation focused"],
            growth_potential="medium"
        )
    ]

def get_recent_applications() -> List[Dict]:
    """Get recent job applications from database using core session.
    
    Returns:
        List of recent job applications with relevant data
    """
    try:
        with get_session() as session:
            # Get applications from last 30 days
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            applications = session.query(JobApplication).filter(
                JobApplication.application_date >= cutoff
            ).order_by(JobApplication.application_date.desc()).all()
            
            return [app.to_dict() for app in applications]
            
    except Exception as e:
        logger.error(f"Error getting recent applications: {str(e)}")
        return []

def get_high_priority_jobs() -> List[Dict]:
    """Get high priority jobs from database using core session.
    
    Returns:
        List of high priority jobs needing attention
    """
    try:
        with get_session() as session:
            jobs = session.query(JobCache).filter(
                JobCache.application_priority == 'high'
            ).order_by(
                JobCache.match_score.desc()
            ).limit(10).all()
            
            return [job.to_dict() for job in jobs]
            
    except Exception as e:
        logger.error(f"Error getting high priority jobs: {str(e)}")
        return []

def get_target_roles_from_profile() -> List[str]:
    """Get target role names from database using core session.
    
    Returns:
        List of target role names to search for
    """
    try:
        with get_session() as session:
            roles = session.query(TargetRole).order_by(
                TargetRole.priority.desc()
            ).all()
            
            return [role.role_name for role in roles]
            
    except Exception as e:
        logger.error(f"Error getting target roles: {str(e)}")
        return []

def get_market_position(company: str) -> str:
    """Get company's market position using core AI engine.
    
    Args:
        company: Company name to analyze
        
    Returns:
        Market position description
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze {company}'s market position considering:
1. Industry standing
2. Market share
3. Competitive advantages
4. Growth trajectory

Provide a one-sentence summary."""
        )
        return result or "Unknown market position"
        
    except Exception as e:
        logger.error(f"Error getting market position: {str(e)}")
        return "Unknown market position"

def analyze_growth(company: str) -> str:
    """Analyze company's growth trajectory using core AI engine.
    
    Args:
        company: Company name to analyze
        
    Returns:
        Growth analysis
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze {company}'s growth trajectory considering:
1. Recent expansion
2. Hiring trends
3. Product/service development
4. Industry outlook

Provide a one-sentence summary."""
        )
        return result or "Unknown growth trajectory"
        
    except Exception as e:
        logger.error(f"Error analyzing growth: {str(e)}")
        return "Unknown growth trajectory"

def get_development_opportunities(job: JobAnalysis) -> List[str]:
    """Get development opportunities from job using core AI engine.
    
    Args:
        job: Job analysis to extract opportunities from
        
    Returns:
        List of development opportunities
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze this job's development opportunities:

Title: {job.title}
Company: {job.company}
Requirements: {', '.join(job.key_requirements)}

List 3-5 specific development opportunities in this role."""
        )
        
        if result:
            # Split into list and clean up
            opportunities = [
                opp.strip('- ').strip()
                for opp in result.split('\n')
                if opp.strip()
            ]
            return opportunities[:5]  # Limit to 5
            
        return []
        
    except Exception as e:
        logger.error(f"Error getting development opportunities: {str(e)}")
        return []

def validate_strategy_content(strategy: DailyStrategy) -> bool:
    """Validate the content of the strategy
    
    Args:
        strategy: DailyStrategy to validate
        
    Returns:
        bool: Whether the strategy is valid
    """
    if not strategy:
        return False
        
    try:
        _ = DailyStrategy(**strategy.model_dump()) if isinstance(strategy, DailyStrategy) else DailyStrategy(**strategy)
        return True
    except Exception as e:
        logger.warning(f"Strategy validation failed: {e}")
        return False

def create_default_strategy() -> DailyStrategy:
    """Create a default strategy with basic content"""
    return DailyStrategy(
        focus_area="Apply to Priority Jobs",
        goals=[
            "Focus on applying to highest priority roles",
            "Review existing applications",
            "Research target companies"
        ],
        action_items=[
            ActionItem(
                description="Review and apply to high priority job matches",
                priority="high",
                deadline="EOD",
                metrics=["3 applications submitted"]
            ),
            ActionItem(
                description="Research target companies",
                priority="medium",
                deadline="EOD",
                metrics=["3 companies researched"]
            )
        ],
        resources_needed=[
            "Job search platform access",
            "Updated resume",
            "Company research tools"
        ],
        success_metrics={
            "applications": "3 quality applications submitted",
            "research": "3 companies thoroughly researched",
            "networking": "2 meaningful professional connections"
        }
    )

def enhance_with_default_content(strategy: Optional[Union[Dict, DailyStrategy]] = None) -> DailyStrategy:
    """Enhance strategy with default content
    
    Args:
        strategy: Optional existing strategy to enhance
        
    Returns:
        DailyStrategy: Enhanced strategy
    """
    try:
        # If we have a strategy, try to convert/validate it
        if strategy:
            if isinstance(strategy, DailyStrategy):
                return strategy
            return DailyStrategy(**strategy)
    except Exception as e:
        logger.warning(f"Error converting existing strategy, using default: {e}")
    
    # Create default strategy if conversion failed or no strategy provided
    return create_default_strategy()

def get_sample_jobs() -> List[JobMatch]:
    """Provide sample job data for fallback
    
    Returns:
        List[JobMatch]: List of sample job matches
    """
    return [
        JobMatch(
            title="Senior Cloud Engineer",
            company="Sample Tech Co A",
            match_score=95,  # Score from 0-100
            application_priority="high",
            key_requirements=["AWS", "Kubernetes", "Terraform"],
            culture_indicators=["Remote-first", "Strong engineering culture"],
            growth_potential="high"
        ),
        JobMatch(
            title="DevOps Team Lead",
            company="Sample Tech Co B",
            match_score=90,  # Score from 0-100
            application_priority="medium",
            key_requirements=["CI/CD", "Team Leadership", "Cloud Platforms"],
            culture_indicators=["Work-life balance", "Mentorship focus"],
            growth_potential="high"
        ),
        JobMatch(
            title="Platform Engineer",
            company="Sample Tech Co C",
            match_score=75,  # Score from 0-100
            application_priority="medium",
            key_requirements=["Infrastructure as Code", "Cloud Architecture", "Python"],
            culture_indicators=["Startup environment", "Innovation focused"],
            growth_potential="medium"
        )
    ]

def get_recent_applications() -> List[Dict]:
    """Get recent job applications from database using core session.
    
    Returns:
        List of recent job applications with relevant data
    """
    try:
        with get_session() as session:
            # Get applications from last 30 days
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            applications = session.query(JobApplication).filter(
                JobApplication.application_date >= cutoff
            ).order_by(JobApplication.application_date.desc()).all()
            
            return [app.to_dict() for app in applications]
            
    except Exception as e:
        logger.error(f"Error getting recent applications: {str(e)}")
        return []

def get_high_priority_jobs() -> List[Dict]:
    """Get high priority jobs from database using core session.
    
    Returns:
        List of high priority jobs needing attention
    """
    try:
        with get_session() as session:
            jobs = session.query(JobCache).filter(
                JobCache.application_priority == 'high'
            ).order_by(
                JobCache.match_score.desc()
            ).limit(10).all()
            
            return [job.to_dict() for job in jobs]
            
    except Exception as e:
        logger.error(f"Error getting high priority jobs: {str(e)}")
        return []

def get_target_roles_from_profile() -> List[str]:
    """Get target role names from database using core session.
    
    Returns:
        List of target role names to search for
    """
    try:
        with get_session() as session:
            roles = session.query(TargetRole).order_by(
                TargetRole.priority.desc()
            ).all()
            
            return [role.role_name for role in roles]
            
    except Exception as e:
        logger.error(f"Error getting target roles: {str(e)}")
        return []

def get_market_position(company: str) -> str:
    """Get company's market position using core AI engine.
    
    Args:
        company: Company name to analyze
        
    Returns:
        Market position description
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze {company}'s market position considering:
1. Industry standing
2. Market share
3. Competitive advantages
4. Growth trajectory

Provide a one-sentence summary."""
        )
        return result or "Unknown market position"
        
    except Exception as e:
        logger.error(f"Error getting market position: {str(e)}")
        return "Unknown market position"

def analyze_growth(company: str) -> str:
    """Analyze company's growth trajectory using core AI engine.
    
    Args:
        company: Company name to analyze
        
    Returns:
        Growth analysis
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze {company}'s growth trajectory considering:
1. Recent expansion
2. Hiring trends
3. Product/service development
4. Industry outlook

Provide a one-sentence summary."""
        )
        return result or "Unknown growth trajectory"
        
    except Exception as e:
        logger.error(f"Error analyzing growth: {str(e)}")
        return "Unknown growth trajectory"

def get_development_opportunities(job: JobAnalysis) -> List[str]:
    """Get development opportunities from job using core AI engine.
    
    Args:
        job: Job analysis to extract opportunities from
        
    Returns:
        List of development opportunities
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze this job's development opportunities:

Title: {job.title}
Company: {job.company}
Requirements: {', '.join(job.key_requirements)}

List 3-5 specific development opportunities in this role."""
        )
        
        if result:
            # Split into list and clean up
            opportunities = [
                opp.strip('- ').strip()
                for opp in result.split('\n')
                if opp.strip()
            ]
            return opportunities[:5]  # Limit to 5
            
        return []
        
    except Exception as e:
        logger.error(f"Error getting development opportunities: {str(e)}")
        return []

def validate_strategy_content(strategy: DailyStrategy) -> bool:
    """Validate the content of the strategy
    
    Args:
        strategy: DailyStrategy to validate
        
    Returns:
        bool: Whether the strategy is valid
    """
    if not strategy:
        return False
        
    try:
        _ = DailyStrategy(**strategy.model_dump()) if isinstance(strategy, DailyStrategy) else DailyStrategy(**strategy)
        return True
    except Exception as e:
        logger.warning(f"Strategy validation failed: {e}")
        return False

def create_default_strategy() -> DailyStrategy:
    """Create a default strategy with basic content"""
    return DailyStrategy(
        focus_area="Apply to Priority Jobs",
        goals=[
            "Focus on applying to highest priority roles",
            "Review existing applications",
            "Research target companies"
        ],
        action_items=[
            ActionItem(
                description="Review and apply to high priority job matches",
                priority="high",
                deadline="EOD",
                metrics=["3 applications submitted"]
            ),
            ActionItem(
                description="Research target companies",
                priority="medium",
                deadline="EOD",
                metrics=["3 companies researched"]
            )
        ],
        resources_needed=[
            "Job search platform access",
            "Updated resume",
            "Company research tools"
        ],
        success_metrics={
            "applications": "3 quality applications submitted",
            "research": "3 companies thoroughly researched",
            "networking": "2 meaningful professional connections"
        }
    )

def enhance_with_default_content(strategy: Optional[Union[Dict, DailyStrategy]] = None) -> DailyStrategy:
    """Enhance strategy with default content
    
    Args:
        strategy: Optional existing strategy to enhance
        
    Returns:
        DailyStrategy: Enhanced strategy
    """
    try:
        # If we have a strategy, try to convert/validate it
        if strategy:
            if isinstance(strategy, DailyStrategy):
                return strategy
            return DailyStrategy(**strategy)
    except Exception as e:
        logger.warning(f"Error converting existing strategy, using default: {e}")
    
    # Create default strategy if conversion failed or no strategy provided
    return create_default_strategy()

def get_sample_jobs() -> List[JobMatch]:
    """Provide sample job data for fallback
    
    Returns:
        List[JobMatch]: List of sample job matches
    """
    return [
        JobMatch(
            title="Senior Cloud Engineer",
            company="Sample Tech Co A",
            match_score=95,  # Score from 0-100
            application_priority="high",
            key_requirements=["AWS", "Kubernetes", "Terraform"],
            culture_indicators=["Remote-first", "Strong engineering culture"],
            growth_potential="high"
        ),
        JobMatch(
            title="DevOps Team Lead",
            company="Sample Tech Co B",
            match_score=90,  # Score from 0-100
            application_priority="medium",
            key_requirements=["CI/CD", "Team Leadership", "Cloud Platforms"],
            culture_indicators=["Work-life balance", "Mentorship focus"],
            growth_potential="high"
        ),
        JobMatch(
            title="Platform Engineer",
            company="Sample Tech Co C",
            match_score=75,  # Score from 0-100
            application_priority="medium",
            key_requirements=["Infrastructure as Code", "Cloud Architecture", "Python"],
            culture_indicators=["Startup environment", "Innovation focused"],
            growth_potential="medium"
        )
    ]

def get_recent_applications() -> List[Dict]:
    """Get recent job applications from database using core session.
    
    Returns:
        List of recent job applications with relevant data
    """
    try:
        with get_session() as session:
            # Get applications from last 30 days
            cutoff = (datetime.now() - timedelta(days=30)).isoformat()
            applications = session.query(JobApplication).filter(
                JobApplication.application_date >= cutoff
            ).order_by(JobApplication.application_date.desc()).all()
            
            return [app.to_dict() for app in applications]
            
    except Exception as e:
        logger.error(f"Error getting recent applications: {str(e)}")
        return []

def get_high_priority_jobs() -> List[Dict]:
    """Get high priority jobs from database using core session.
    
    Returns:
        List of high priority jobs needing attention
    """
    try:
        with get_session() as session:
            jobs = session.query(JobCache).filter(
                JobCache.application_priority == 'high'
            ).order_by(
                JobCache.match_score.desc()
            ).limit(10).all()
            
            return [job.to_dict() for job in jobs]
            
    except Exception as e:
        logger.error(f"Error getting high priority jobs: {str(e)}")
        return []

def get_target_roles_from_profile() -> List[str]:
    """Get target role names from database using core session.
    
    Returns:
        List of target role names to search for
    """
    try:
        with get_session() as session:
            roles = session.query(TargetRole).order_by(
                TargetRole.priority.desc()
            ).all()
            
            return [role.role_name for role in roles]
            
    except Exception as e:
        logger.error(f"Error getting target roles: {str(e)}")
        return []

def get_market_position(company: str) -> str:
    """Get company's market position using core AI engine.
    
    Args:
        company: Company name to analyze
        
    Returns:
        Market position description
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze {company}'s market position considering:
1. Industry standing
2. Market share
3. Competitive advantages
4. Growth trajectory

Provide a one-sentence summary."""
        )
        return result or "Unknown market position"
        
    except Exception as e:
        logger.error(f"Error getting market position: {str(e)}")
        return "Unknown market position"

def analyze_growth(company: str) -> str:
    """Analyze company's growth trajectory using core AI engine.
    
    Args:
        company: Company name to analyze
        
    Returns:
        Growth analysis
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze {company}'s growth trajectory considering:
1. Recent expansion
2. Hiring trends
3. Product/service development
4. Industry outlook

Provide a one-sentence summary."""
        )
        return result or "Unknown growth trajectory"
        
    except Exception as e:
        logger.error(f"Error analyzing growth: {str(e)}")
        return "Unknown growth trajectory"

def get_development_opportunities(job: JobAnalysis) -> List[str]:
    """Get development opportunities from job using core AI engine.
    
    Args:
        job: Job analysis to extract opportunities from
        
    Returns:
        List of development opportunities
    """
    try:
        result = ai_engine.generate_text(
            prompt=f"""Analyze this job's development opportunities:

Title: {job.title}
Company: {job.company}
Requirements: {', '.join(job.key_requirements)}

List 3-5 specific development opportunities in this role."""
        )
        
        if result:
            # Split into list and clean up
            opportunities = [
                opp.strip('- ').strip()
                for opp in result.split('\n')
                if opp.strip()
            ]
            return opportunities[:5]  # Limit to 5
            
        return []
        
    except Exception as e:
        logger.error(f"Error getting development opportunities: {str(e)}")
        return []