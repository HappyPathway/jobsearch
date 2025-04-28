"""Medium article generation and publishing using core components."""
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from jobsearch.core.logging import setup_logging
from jobsearch.core.storage import GCSManager
from jobsearch.core.database import get_session
from jobsearch.core.ai import AIEngine
from jobsearch.core.markdown import MarkdownGenerator
from jobsearch.core.schemas import ArticleContent, ArticleMetadata
from jobsearch.core.http import HttpClient
from jobsearch.core.models import Experience, Skill

# Initialize core components
logger = setup_logging('medium_publisher')
storage = GCSManager()
ai_engine = AIEngine(feature_name='content_generation')
markdown = MarkdownGenerator()
http = HttpClient()

async def generate_article(topic: str, experiences: List[Dict], skills: List[str]) -> Optional[ArticleContent]:
    """Generate Medium article using core AI engine.
    
    Args:
        topic: Article topic 
        experiences: Relevant experience data
        skills: Relevant skills
        
    Returns:
        Generated article content or None on failure
    """
    try:
        result = await ai_engine.generate(
            prompt=f"""Generate a professional blog post about:
{topic}

Drawing from these experiences:
{markdown.format_experiences(experiences)}

And these skills:
{markdown.format_skills(skills)}

Requirements:
1. Technical depth and accuracy
2. Personal insights and stories
3. Professional tone
4. Clear structure with sections
5. SEO-friendly title""",
            output_type=ArticleContent
        )
        
        if result:
            logger.info(f"Generated article: {result.title}")
            return result
            
        logger.error("Failed to generate article")
        return None
        
    except Exception as e:
        logger.error(f"Error generating article: {str(e)}")
        return None

def format_article(article: ArticleContent) -> str:
    """Format article content for Medium."""
    try:
        return markdown.format_article(
            title=article.title,
            subtitle=article.subtitle,
            sections=article.sections,
            tags=article.tags
        )
    except Exception as e:
        logger.error(f"Error formatting article: {str(e)}")
        return ""

def get_relevant_experiences(topic: str) -> List[Dict]:
    """Get relevant experiences for article topic."""
    try:
        with get_session() as session:
            experiences = session.query(Experience).all()
            return [
                {
                    "company": exp.company,
                    "title": exp.title,
                    "description": exp.description
                }
                for exp in experiences
                if any(keyword.lower() in exp.description.lower() for keyword in topic.split())
            ]
    except Exception as e:
        logger.error(f"Error getting experiences: {str(e)}")
        return []

async def store_article(article: ArticleContent) -> bool:
    """Store article in cloud storage."""
    try:
        date = datetime.now().strftime("%Y-%m-%d")
        filename = f"articles/{date}_{article.slug}.md"
        
        content = format_article(article)
        storage.write_text(filename, content)
        
        logger.info(f"Stored article at {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing article: {str(e)}")
        return False

async def publish_article(article: ArticleContent) -> bool:
    """Publish article to Medium."""
    try:
        content = format_article(article)
        response = await http.post_medium_article(
            title=article.title,
            content=content,
            tags=article.tags
        )
        
        if response.success:
            logger.info(f"Published article to Medium: {response.url}")
            return True
            
        logger.error(f"Failed to publish article: {response.error}")
        return False
        
    except Exception as e:
        logger.error(f"Error publishing article: {str(e)}")
        return False

async def main() -> int:
    """Main entry point for article generation."""
    try:
        # Get topic from args
        import sys
        if len(sys.argv) < 2:
            logger.error("Usage: generate_article.py <topic>")
            return 1
            
        topic = sys.argv[1]
        logger.info(f"Generating article about: {topic}")
        
        # Get relevant data
        experiences = get_relevant_experiences(topic)
        if not experiences:
            logger.error("No relevant experiences found for topic")
            return 1
            
        with get_session() as session:
            skills = [
                skill.skill_name
                for skill in session.query(Skill).all()
                if any(keyword.lower() in skill.skill_name.lower() for keyword in topic.split())
            ]
            
        # Generate and store article
        article = await generate_article(topic, experiences, skills)
        if not article:
            return 1
            
        if not await store_article(article):
            return 1
            
        # Optionally publish
        if "--publish" in sys.argv:
            if not await publish_article(article):
                return 1
                
        return 0
        
    except Exception as e:
        logger.error(f"Error in article generation: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))