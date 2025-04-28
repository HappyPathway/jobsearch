"""Web presence content generation using monitored LLM interactions."""
from typing import Optional, List

from jobsearch.core.llm_agent import BaseLLMAgent
from jobsearch.core.schemas import (
    Article, ArticleSection, GithubPagesSummary,
    ProfessionalSummary, Tagline
)
from jobsearch.core.logging import setup_logging

logger = setup_logging('web_presence_agent')

class WebPresenceAgent(BaseLLMAgent):
    """Agent for generating web content."""
    
    def __init__(self):
        super().__init__(
            feature_name='web_presence',
            output_type=None  # Varies by method
        )
        
    async def generate_tagline(
        self,
        recent_role: str,
        top_skills: List[str],
        target_role: Optional[str] = None
    ) -> Optional[str]:
        """Generate a professional tagline.
        
        Args:
            recent_role: Most recent job title
            top_skills: List of key skills
            target_role: Optional target role
            
        Returns:
            Professional tagline, or None on error
        """
        example_data = Tagline(
            tagline="Senior Cloud Architect Specializing in Enterprise Digital Transformation"
        ).model_dump()
        
        prompt = f"""Create a short, impactful professional tagline (one line, no more than 10 words).
Focus on core expertise and career level.

Current Role: {recent_role}
Top Skills: {', '.join(top_skills)}
{f'Target Role: {target_role}' if target_role else ''}

The tagline should:
1. Be concise and memorable
2. Highlight core expertise
3. Target senior/leadership roles
4. Use impactful keywords"""

        result = await self.generate(
            prompt=prompt,
            expected_type=Tagline,
            example_data=example_data
        )
        
        return result.tagline if result else None
        
    async def generate_technical_article(
        self,
        topic: str,
        expertise_level: str = "advanced",
        target_length: int = 1500
    ) -> Optional[Article]:
        """Generate a technical article.
        
        Args:
            topic: Article topic
            expertise_level: Target expertise level
            target_length: Approximate word count
            
        Returns:
            Structured article content, or None on error
        """
        example_data = Article(
            title="Building Resilient Cloud Architecture: Best Practices and Patterns",
            introduction="In today's rapidly evolving tech landscape...",
            sections=[
                ArticleSection(
                    heading="Understanding Cloud Architecture Fundamentals",
                    content=[
                        "Cloud architecture is the foundation of modern infrastructure",
                        "Key components include compute, storage, and networking",
                    ],
                    key_points=["Cloud services fundamentals", "Architecture patterns"],
                    code_examples=["# Example infrastructure code"]
                )
            ],
            tags=["Cloud Computing", "Architecture", "Technology"]
        ).model_dump()
        
        prompt = f"""Create a detailed technical article about {topic}.
Target audience: {expertise_level} level developers
Approximate length: {target_length} words

The article should:
1. Have a compelling title
2. Include an engaging introduction
3. Break content into clear sections
4. Include code examples where relevant
5. Highlight key takeaways
6. Use appropriate technical depth
7. Include relevant tags

Structure the content for clear understanding and maintain technical accuracy."""

        return await self.generate(
            prompt=prompt,
            expected_type=Article,
            example_data=example_data
        )
