"""Generate and manage GitHub Pages for professional portfolio."""
from pathlib import Path
import tempfile
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.models import Experience, Skill, ResumeSection, TargetRole
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import AIEngine
from jobsearch.core.markdown import MarkdownGenerator
from jobsearch.core.schemas import WebPresenceContent, GithubPagesSummary

# Initialize core components
logger = setup_logging('github_pages')
storage = GCSManager()
ai_engine = AIEngine(feature_name='web_presence')
markdown = MarkdownGenerator()

async def generate_tagline(experiences: list, skills: list, target_roles: list) -> str:
    """Generate a professional tagline using core AI Engine."""
    try:
        result = await ai_engine.generate(
            prompt=f"""Create a professional tagline based on:
            
Experience Highlights:
{markdown.format_experiences(experiences[:3])}

Core Skills:
{markdown.format_skills(skills[:5])}

Target Roles:
{markdown.format_target_roles(target_roles[:3])}
""",
            output_type=WebPresenceContent
        )
        
        if result:
            logger.info(f"Generated tagline: {result.tagline}")
            return result.tagline
        
        logger.error("Failed to generate tagline")
        return ""
        
    except Exception as e:
        logger.error(f"Error generating tagline: {str(e)}")
        return ""

async def generate_professional_summary(experiences: list, skills: list, target_roles: list) -> str:
    """Generate a professional summary using core AI Engine."""
    try:
        result = await ai_engine.generate(
            prompt=f"""Create a professional summary based on:

Experience History:
{markdown.format_experiences(experiences)}

Skills and Expertise:
{markdown.format_skills(skills)}

Career Goals:
{markdown.format_target_roles(target_roles)}
""",
            output_type=GithubPagesSummary
        )
        
        if result:
            summary = markdown.format_summary(
                title=result.title,
                highlights=result.highlights,
                skills=result.skills,
                goals=result.goals
            )
            storage.save_markdown('pages/summary.md', summary)
            return summary
            
        logger.error("Failed to generate summary")
        return ""
        
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return ""

async def generate_pages() -> bool:
    """Generate static GitHub Pages and store in GCS."""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Get profile data
            with get_session() as session:
                experiences = session.query(Experience).order_by(Experience.end_date.desc()).all()
                skills = session.query(Skill).all()
                target_roles = session.query(TargetRole).order_by(TargetRole.match_score.desc()).all()
                sections = dict(session.query(ResumeSection.section_name, ResumeSection.content).all())
            
            # Generate content
            tagline = await generate_tagline(experiences, skills, target_roles)
            summary = await generate_professional_summary(experiences, skills, target_roles)
            
            # Prepare template data
            profile = {
                'tagline': tagline,
                'summary': summary,
                'sections': sections,
                'experiences': experiences,
                'skills': skills,
                'target_roles': target_roles,
                'current_date': datetime.now().strftime('%B %d, %Y')
            }
            
            # Render template
            env = Environment(loader=FileSystemLoader(Path(__file__).parent / 'templates'))
            template = env.get_template('github_pages.html')
            html = template.render(**profile)
            
            # Save to GCS
            temp_index = temp_dir_path / 'index.html'
            temp_index.write_text(html)
            storage.save_file('pages/index.html', temp_index)
            
            # Copy static assets if they exist
            static_dir = Path(__file__).parent / 'static'
            if static_dir.exists():
                for file in static_dir.rglob('*'):
                    if file.is_file():
                        rel_path = file.relative_to(static_dir)
                        storage.save_file(f'pages/static/{rel_path}', file)
            
            logger.info("Successfully generated GitHub Pages")
            return True
            
    except Exception as e:
        logger.error(f"Error generating GitHub Pages: {str(e)}")
        return False

async def main() -> int:
    """Main entry point for GitHub Pages generation."""
    try:
        if await generate_pages():
            logger.info("Successfully published GitHub Pages")
            return 0
        else:
            logger.error("Failed to generate GitHub Pages")
            return 1
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))