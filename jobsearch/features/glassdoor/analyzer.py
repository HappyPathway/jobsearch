"""Glassdoor company data analysis using Gemini AI."""

from typing import Dict, Optional
import time
from jobsearch.core.ai import StructuredPrompt
from jobsearch.core.logging import setup_logging
from jobsearch.core.schemas import GlassdoorAnalysis

logger = setup_logging('glassdoor_analyzer')

class GlassdoorAnalyzer:
    """Analyzes Glassdoor company data using Gemini AI."""
    
    def __init__(self, api_key: str):
        """Initialize with Gemini API key."""
        self.prompt_helper = StructuredPrompt()
    
    def analyze_company(self, company_name: str, scraped_data: Dict) -> Dict:
        """Analyze company data and provide insights."""
        try:
            # Prepare review text
            review_texts = [
                f"{r['title']}: Pros - {r['pros']}, Cons - {r['cons']}"
                for r in scraped_data.get('reviews', [])
            ]
            
            # Create analysis prompt
            prompt = f"""
            Analyze this Glassdoor data for {company_name}:
            Reviews: {review_texts}
            Ratings: {scraped_data.get('ratings', {})}
            
            Provide a structured analysis of:
            1. Major cultural red flags
            2. Work-life balance assessment
            3. Management quality indicators
            4. Overall recommendation
            """
            
            # Get structured analysis
            analysis = self.prompt_helper.get_structured_response(
                prompt=prompt,
                expected_structure=GlassdoorAnalysis,
                example_data=GlassdoorAnalysis(
                    red_flags=["High turnover rate", "Limited career growth"],
                    work_life_balance="Good work-life balance with flexible hours",
                    management_quality="Mixed reviews on management effectiveness",
                    recommendation="Consider with caution"
                ).model_dump()
            )
            
            if analysis:
                # Add raw data and cache timestamp
                analysis['raw_data'] = scraped_data
                analysis['timestamp'] = time.time()
                return analysis
            
            logger.error(f"Failed to get analysis for company {company_name}")
            return {
                'error': 'Failed to generate analysis',
                'raw_data': scraped_data,
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing company {company_name}: {e}")
            return {
                'error': str(e),
                'raw_data': scraped_data,
                'timestamp': time.time()
            }