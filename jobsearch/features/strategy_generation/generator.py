"""Job search strategy generation using core components."""
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import AIEngine
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.models import (
    Experience, 
    Skill, 
    TargetRole, 
    JobCache, 
    JobApplication,
    RecruiterContact
)
from jobsearch.core.markdown import MarkdownGenerator
from jobsearch.core.schemas import (
    DailyStrategy,
    ActionItem,
    FocusArea,
    NetworkingTarget,
    WeeklyFocus,
    RecentActivity,
    ProfileData,
    CompanyInsight
)

# Initialize core components
logger = setup_logging('strategy_generator')
storage = GCSManager()
ai_engine = AIEngine(feature_name='strategy_generation')
markdown = MarkdownGenerator()
monitoring = setup_monitoring('strategy_generation')

def get_recent_activity() -> RecentActivity:
    """Get recent jobs and applications from database."""
    try:
        with get_session() as session:
            # Get recent job applications 
            recent_apps = session.query(JobApplication).join(
                JobCache
            ).order_by(
                JobApplication.application_date.desc()
            ).limit(5).all()
            
            app_data = []
            for app in recent_apps:
                app_data.append({
                    'job_title': app.job.title,
                    'company': app.job.company,
                    'status': app.status,
                    'date': app.application_date,
                    'notes': app.notes
                })
                
            # Get recent found jobs
            recent_jobs = session.query(JobCache).order_by(
                JobCache.first_seen_date.desc()
            ).limit(10).all()
            
            job_data = []
            for job in recent_jobs:
                job_data.append({
                    'title': job.title,
                    'company': job.company,
                    'match_score': job.match_score,
                    'url': job.url
                })
                
            return RecentActivity(
                applications=app_data,
                discovered_jobs=job_data
            )
            
    except Exception as e:
        logger.error(f"Error getting recent activity: {str(e)}")
        return RecentActivity(applications=[], discovered_jobs=[])

def get_profile_data() -> ProfileData:
    """Get current profile data for strategy generation."""
    try:
        with get_session() as session:
            # Get experiences in order
            experiences = session.query(Experience).order_by(
                Experience.end_date.desc(),
                Experience.start_date.desc()
            ).all()
            
            experience_data = []
            for exp in experiences:
                experience_data.append({
                    'company': exp.company,
                    'title': exp.title,
                    'description': exp.description,
                    'skills': [skill.skill_name for skill in exp.skills]
                })
            
            # Get unique skills
            skills = session.query(Skill).all()
            skill_names = [skill.skill_name for skill in skills]
            
            # Get target roles
            roles = session.query(TargetRole).order_by(
                TargetRole.priority.desc()
            ).all()
            target_roles = [role.role_name for role in roles]
            
            return ProfileData(
                experiences=experience_data,
                skills=skill_names,
                target_roles=target_roles
            )
            
    except Exception as e:
        logger.error(f"Error getting profile data: {str(e)}")
        return ProfileData(experiences=[], skills=[], target_roles=[])

def get_networking_targets() -> List[NetworkingTarget]:
    """Get potential networking targets from database."""
    try:
        with get_session() as session:
            # Get identified but not contacted recruiters
            recruiters = session.query(RecruiterContact).filter(
                RecruiterContact.status == 'identified'
            ).all()
            
            targets = []
            for rec in recruiters:
                targets.append(NetworkingTarget(
                    name=rec.name,
                    title=rec.title,
                    company=rec.company,
                    source=rec.source,
                    url=rec.url,
                    notes=rec.notes
                ))
                
            return targets
            
    except Exception as e:
        logger.error(f"Error getting networking targets: {str(e)}")
        return []

async def generate_daily_strategy() -> DailyStrategy:
    """Generate daily job search strategy using core AI engine."""
    try:
        logger.info("Generating daily job search strategy")
        monitoring.increment('strategy_generation')
        
        # Get input data
        recent = get_recent_activity()
        profile = get_profile_data()
        targets = get_networking_targets()
        
        # Use AI engine for strategy generation
        strategy = await ai_engine.generate(
            prompt=f"""Generate a daily job search strategy based on:

RECENT ACTIVITY
Applications: {len(recent.applications)} in last week
New Jobs Found: {len(recent.discovered_jobs)} matching profile
Latest Application: {recent.applications[0].get('status') if recent.applications else 'None'}

CURRENT PROFILE
Skills: {', '.join(profile.skills[:5])}... ({len(profile.skills)} total)
Target Roles: {', '.join(profile.target_roles)}
Latest Experience: {profile.experiences[0].get('title')} at {profile.experiences[0].get('company')}

NETWORKING
Potential Contacts: {len(targets)} identified recruiters/contacts""",
            output_type=DailyStrategy
        )
        
        if strategy:
            monitoring.track_success('strategy_generation')
            # Save strategy to markdown file
            strategy_path = f"strategies/strategy_{datetime.now().strftime('%Y-%m-%d')}.md"
            strategy_md = markdown.format_strategy(strategy)
            storage.write_file(strategy_path, strategy_md)
            logger.info(f"Strategy saved to {strategy_path}")
            return strategy
            
        monitoring.track_failure('strategy_generation')
        logger.error("Failed to generate strategy")
        return None
        
    except Exception as e:
        monitoring.track_error('strategy_generation', str(e))
        logger.error(f"Error generating strategy: {str(e)}")
        return None

async def main() -> int:
    """Main entry point."""
    try:
        logger.info("Starting strategy generation")
        strategy = await generate_daily_strategy()
        
        if strategy:
            logger.info("Successfully generated daily strategy")
            return 0
            
        logger.error("Failed to generate strategy")
        return 1
        
    except Exception as e:
        logger.error(f"Error in strategy generation: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))