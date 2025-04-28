"""Job search strategy generation and planning."""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv

from ..core.ai import StructuredPrompt
from ..core.logging import setup_logging
from jobsearch.core.models import (
    Experience, Skill, TargetRole, JobCache, JobApplication
)
from jobsearch.core.database import get_session
from jobsearch.core.storage import gcs
from .common import JobInfo, get_today

logger = setup_logging('strategy_generator')

# Configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_profile_summary() -> Dict:
    """Get summarized profile data from database"""
    with get_session() as session:
        experiences = []
        skills = set()
        
        # Get experiences and skills
        for exp in session.query(Experience).all():
            experiences.append({
                'company': exp.company,
                'title': exp.title,
                'start_date': exp.start_date,
                'end_date': exp.end_date,
                'description': exp.description,
                'skills': [skill.skill_name for skill in exp.skills]
            })
            for skill in exp.skills:
                skills.add(skill.skill_name)
                
        # Get target roles
        target_roles = []
        for role in session.query(TargetRole).all():
            target_roles.append({
                'role_name': role.role_name,
                'priority': role.priority,
                'match_score': role.match_score,
                'requirements': json.loads(role.requirements) if role.requirements else [],
                'next_steps': json.loads(role.next_steps) if role.next_steps else []
            })
            
        return {
            'experiences': experiences,
            'skills': list(skills),
            'target_roles': target_roles
        }

def get_recent_applications() -> List[Dict]:
    """Get recent job applications from database"""
    with get_session() as session:
        applications = []
        for app in session.query(JobApplication).order_by(
            JobApplication.application_date.desc()
        ).limit(10):
            applications.append({
                'company': app.job.company,
                'title': app.job.title,
                'date': app.application_date,
                'status': app.status
            })
        return applications

def get_high_priority_jobs() -> List[Dict]:
    """Get high priority jobs from database"""
    with get_session() as session:
        jobs = []
        for job in session.query(JobCache).filter(
            JobCache.application_priority == 'high'
        ).order_by(JobCache.match_score.desc()).all():
            jobs.append({
                'url': job.url,
                'title': job.title,
                'company': job.company,
                'match_score': job.match_score,
                'key_requirements': json.loads(job.key_requirements) if job.key_requirements else [],
                'culture_indicators': json.loads(job.culture_indicators) if job.culture_indicators else [],
                'career_growth_potential': job.career_growth_potential
            })
        return jobs

from jobsearch.core.schemas import (
    DailyStrategy, 
    ActionItem, 
    JobMatch, 
    CompanyInsight,
    CompanyAnalysis
)

def generate_daily_strategy(profile_data: Dict, recent_applications: List[Dict], priority_jobs: List[Dict]) -> Optional[DailyStrategy]:
    """Generate a daily job search strategy using Gemini
    
    Args:
        profile_data: Profile information including skills and experience
        recent_applications: List of recent job applications
        priority_jobs: List of high priority job opportunities
    
    Returns:
        DailyStrategy model if successful, None if generation fails
    """
    try:
        # Generate strategy content using AI
        action_items = []
        for priority_job in priority_jobs[:3]:  # Top 3 priority jobs
            action_items.append(
                ActionItem(
                    description=f"Apply to {priority_job['title']} at {priority_job['company']}",
                    priority="high",
                    deadline="EOD",
                    metrics=[
                        "Application submitted",
                        "Resume customized",
                        "Cover letter tailored" 
                    ]
                )
            )
        
        # Convert jobs to JobMatch models
        job_matches = []
        for job in priority_jobs:
            try:
                job_matches.append(JobMatch(
                    title=job.get('title', 'Unknown'),
                    company=job.get('company', 'Unknown'), 
                    match_score=job.get('match_score', 0.0),
                    application_priority=job.get('application_priority', 'medium'),
                    key_requirements=job.get('key_requirements', []),
                    culture_indicators=job.get('culture_indicators', []),
                    growth_potential=job.get('growth_potential', 'Unknown')
                ))
            except Exception as e:
                logger.warning(f"Failed to validate job: {e}")
                continue
                
        # Generate company insights
        company_insights = {}
        for job in job_matches:
            if job.company not in company_insights:
                try:
                    company_insights[job.company] = CompanyInsight(
                        market_position=get_market_position(job.company),
                        growth_trajectory=analyze_growth(job.company),
                        culture_indicators=job.culture_indicators,
                        stability_level="medium",  # Default until we have real data
                        growth_potential="high" if job.growth_potential == "high" else "medium"
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate company insight: {e}")
                    continue

        # Create daily strategy with all components
        strategy = DailyStrategy(
            focus_area="High Priority Job Applications",
            goals=[
                "Submit applications to top matched roles",
                "Research target companies",
                "Follow up on pending applications"
            ],
            action_items=action_items,
            resources_needed=[
                "Updated resume",
                "Cover letter template",
                "Company research materials"
            ],
            success_metrics={
                "applications": "3 high-quality applications submitted",
                "research": "In-depth research on 3 target companies",
                "networking": "2 meaningful industry connections made",
                "skill_development": "1 hour of focused learning"
            },
            jobs=job_matches,
            company_insights=company_insights
        )
        
        return strategy

    except Exception as e:
        logger.error(f"Error generating daily strategy: {str(e)}")
        return None

def store_strategy(strategy: Dict) -> bool:
    """Store strategy in GCS"""
    try:
        today = get_today()
        gcs_path = f'strategies/{today}_strategy.json'
        
        return gcs.safe_upload(json.dumps(strategy, indent=2), gcs_path)
        
    except Exception as e:
        logger.error(f"Error storing strategy: {str(e)}")
        return False

def generate_strategy() -> Dict:
    """Generate and store daily job search strategy"""
    try:
        # Get required data
        profile_data = get_profile_summary()
        recent_applications = get_recent_applications()
        priority_jobs = get_high_priority_jobs()
        
        # Generate strategy
        strategy = generate_daily_strategy(
            profile_data=profile_data,
            recent_applications=recent_applications,
            priority_jobs=priority_jobs
        )
        
        if not strategy:
            return {'success': False, 'error': 'Failed to generate strategy'}
            
        # Store strategy
        if not store_strategy(strategy):
            return {'success': False, 'error': 'Failed to store strategy'}
            
        return {
            'success': True,
            'strategy': strategy
        }
        
    except Exception as e:
        logger.error(f"Error in strategy generation: {str(e)}")
        return {'success': False, 'error': str(e)}

def generate_weekly_focus(job_listings=None) -> str:
    """Generate weekly focus for job search strategy
    
    Args:
        job_listings: Optional list of job listings to consider
        
    Returns:
        str: Weekly focus statement
    """
    try:
        logger.info("Generating weekly focus")
        
        prompt = StructuredPrompt()
        
        # If no job listings provided, check database
        if not job_listings or len(job_listings) == 0:
            try:
                with get_session() as session:
                    # Get application status metrics
                    total_applications = session.query(JobApplication).count()
                    open_applications = session.query(JobApplication).filter(
                        JobApplication.status.in_(['applied', 'submitted', 'pending'])
                    ).count()
                    interview_applications = session.query(JobApplication).filter(
                        JobApplication.status.in_(['interview', 'technical', 'final'])
                    ).count()
                    
                    # Get high priority jobs
                    high_priority_count = session.query(JobCache).filter(
                        JobCache.application_priority == 'high'
                    ).count()
            except Exception as e:
                logger.warning(f"Error getting application metrics: {str(e)}")
                # Set defaults if database access fails
                total_applications = 0
                open_applications = 0
                interview_applications = 0
                high_priority_count = 0
        else:
            # Use provided job listings
            total_applications = len(job_listings)
            high_priority_count = len([j for j in job_listings if j.get('application_priority') == 'high'])
            open_applications = 0
            interview_applications = 0
            
        # Generate weekly focus with AI
        result = prompt.get_structured_response(
            prompt=f"""Generate a weekly focus statement for a job search strategy.
Consider the following metrics:
- Total applications: {total_applications}
- Open applications: {open_applications}
- Interview stage: {interview_applications}
- High-priority job opportunities: {high_priority_count}

The weekly focus should be a concise paragraph (3-5 sentences) that provides strategic direction 
for the week's job search activities.""",
            expected_structure=str,
            temperature=0.3
        )
        
        if result:
            logger.info("Successfully generated weekly focus")
            return result
        else:
            logger.warning("Failed to generate weekly focus, using default")
            return "This week's focus is on targeting high-quality opportunities that align with your career goals. Prioritize applications for roles with strong skills match and growth potential. Allocate time to follow up on existing applications and prepare for potential interviews. Continue networking with industry professionals to discover hidden opportunities."
            
    except Exception as e:
        logger.error(f"Error generating weekly focus: {str(e)}")
        return "This week's focus is on applying to high-priority opportunities while continuing to develop relevant skills. Follow up on existing applications and expand your professional network. Review and refine your application materials based on feedback."