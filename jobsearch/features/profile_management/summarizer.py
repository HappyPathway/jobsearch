"""Profile data combination and summarization using core components."""
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import AIEngine
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.models import (
    Experience, 
    Skill, 
    TargetRole, 
    ResumeSection, 
    CoverLetterSection
)
from jobsearch.core.markdown import MarkdownGenerator
from jobsearch.core.schemas import (
    ProfileData,
    ExperienceData,
    SkillData,
    TargetRoleData,
    ProfessionalSummary,
    Tagline
)

# Initialize core components
logger = setup_logging('profile_summarizer')
storage = GCSManager()
ai_engine = AIEngine(feature_name='profile_summarization') 
markdown = MarkdownGenerator()
monitoring = setup_monitoring('profile')

def fetch_data() -> Tuple[List[ExperienceData], List[SkillData], List[TargetRoleData]]:
    """Get data from database using core database session."""
    try:
        monitoring.increment('fetch_data')
        with get_session() as session:
            # Get experiences in reverse chronological order
            experiences = session.query(Experience).order_by(
                Experience.end_date.desc()
            ).all()
            
            # Build experience data objects
            exp_data = []
            for exp in experiences:
                exp_data.append(ExperienceData(
                    company=exp.company,
                    title=exp.title,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    description=exp.description,
                    skills=[skill.skill_name for skill in exp.skills]
                ))
            
            # Get unique skills
            skills = session.query(Skill).all()
            skill_data = [
                SkillData(skill_name=skill.skill_name)
                for skill in skills
            ]
            
            # Get existing target roles
            roles = session.query(TargetRole).order_by(
                TargetRole.priority.desc()
            ).all()
            role_data = [
                TargetRoleData(
                    role_name=role.role_name,
                    priority=role.priority,
                    match_score=role.match_score,
                    requirements=json.loads(role.requirements) if role.requirements else [],
                    next_steps=json.loads(role.next_steps) if role.next_steps else []
                )
                for role in roles
            ]
            
            monitoring.track_success('fetch_data')
            return exp_data, skill_data, role_data
            
    except Exception as e:
        monitoring.track_error('fetch_data', str(e))
        logger.error(f"Error fetching profile data: {str(e)}")
        return [], [], []

async def generate_summary() -> Optional[ProfessionalSummary]:
    """Generate professional summary using core AI engine."""
    try:
        monitoring.increment('generate_summary')
        experiences, skills, roles = fetch_data()
        
        if not experiences:
            logger.error("No experience data available")
            return None
            
        # Use AI to generate summary
        summary = await ai_engine.generate(
            prompt=f"""Generate a professional summary based on:

EXPERIENCE:
{experiences[:3]}  # Most recent experiences

SKILLS:
{[skill.skill_name for skill in skills]}

TARGET ROLES:
{[role.role_name for role in roles]}

Create a compelling professional summary that:
1. Highlights key achievements
2. Emphasizes relevant skills
3. Shows career progression
4. Aligns with target roles""",
            output_type=ProfessionalSummary
        )
        
        if summary:
            monitoring.track_success('generate_summary')
            return summary
            
        monitoring.track_failure('generate_summary')
        logger.error("Failed to generate summary")
        return None
        
    except Exception as e:
        monitoring.track_error('generate_summary', str(e))
        logger.error(f"Error generating summary: {str(e)}")
        return None

async def generate_tagline() -> Optional[Tagline]:
    """Generate professional tagline using core AI engine."""
    try:
        monitoring.increment('generate_tagline')
        experiences, skills, roles = fetch_data()
        
        if not experiences:
            logger.error("No experience data available")
            return None
            
        # Use AI to generate tagline
        tagline = await ai_engine.generate(
            prompt=f"""Generate a professional tagline based on:

Current Role: {experiences[0].title} at {experiences[0].company}
Top Skills: {[skill.skill_name for skill in skills[:5]]}
Target Roles: {[role.role_name for role in roles]}

Create a concise, impactful tagline that:
1. Captures professional identity
2. Highlights key expertise
3. Aligns with career goals""",
            output_type=Tagline
        )
        
        if tagline:
            monitoring.track_success('generate_tagline')
            return tagline
            
        monitoring.track_failure('generate_tagline')
        logger.error("Failed to generate tagline")
        return None
        
    except Exception as e:
        monitoring.track_error('generate_tagline', str(e))
        logger.error(f"Error generating tagline: {str(e)}")
        return None

async def save_combined_profile() -> bool:
    """Save combined profile markdown file."""
    try:
        monitoring.increment('save_profile')
        
        # Get data components
        summary = await generate_summary()
        tagline = await generate_tagline()
        experiences, skills, roles = fetch_data()
        
        if not summary or not tagline:
            logger.error("Missing required profile components")
            return False
            
        # Generate markdown content
        content = [
            "# Professional Profile\n\n",
            f"## {tagline.tagline}\n\n",
            "## Summary\n\n"
        ]
        
        for para in summary.summary:
            content.append(f"{para}\n\n")
            
        content.append("## Key Points\n\n")
        for point in summary.key_points:
            content.append(f"- {point}\n")
            
        content.append("\n## Experience\n\n")
        for exp in experiences:
            content.extend([
                f"### {exp.title} at {exp.company}\n",
                f"_{exp.start_date} - {exp.end_date}_\n\n",
                f"{exp.description}\n\n",
                "**Skills:** " + ", ".join(exp.skills) + "\n\n"
            ])
            
        content.append("## Skills\n\n")
        content.append(", ".join([skill.skill_name for skill in skills]))
        
        content.append("\n\n## Target Roles\n\n")
        for role in roles:
            content.extend([
                f"### {role.role_name}\n",
                f"Priority: {role.priority}\n",
                f"Match Score: {role.match_score}%\n\n",
                "**Requirements:**\n",
                *[f"- {req}\n" for req in role.requirements],
                "\n**Next Steps:**\n",
                *[f"- {step}\n" for step in role.next_steps],
                "\n"
            ])
            
        # Save to file
        profile_path = Path(__file__).parent.parent.parent.parent / 'combined_profile.md'
        with open(profile_path, 'w') as f:
            f.write(''.join(content))
            
        # Upload to GCS
        storage.upload_file(profile_path, 'profiles/combined_profile.md')
        
        monitoring.track_success('save_profile')
        return True
        
    except Exception as e:
        monitoring.track_error('save_profile', str(e))
        logger.error(f"Error saving combined profile: {str(e)}")
        return False

async def main() -> int:
    """Main entry point."""
    try:
        logger.info("Starting profile summarization")
        if await save_combined_profile():
            logger.info("Successfully generated and saved combined profile")
            return 0
            
        logger.error("Failed to generate combined profile")
        return 1
        
    except Exception as e:
        logger.error(f"Error in profile summarization: {str(e)}")
        return 1

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))
