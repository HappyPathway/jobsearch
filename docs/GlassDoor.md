# Glassdoor Company Analysis Integration

## Overview
Web scraping solution for Glassdoor company data with Gemini AI processing to extract meaningful insights.

## Architecture Components

### 1. Web Scraping Module
- Uses Selenium/Playwright for JavaScript-rendered content
- Handles Glassdoor's anti-bot measures
- Scrapes key data points:
  - Company ratings
  - Reviews (recent 10-20)
  - Pros/Cons sections
  - Culture ratings
  - Work/Life balance scores

### 2. Data Processing with Gemini
```python
class GlassdoorStructuredPrompt(StructuredPrompt):
    company_name: str
    raw_reviews: List[str]
    ratings: Dict[str, float]
    
    template = """
    Analyze this Glassdoor data for {company_name}:
    Reviews: {raw_reviews}
    Ratings: {ratings}
    
    Provide a structured analysis of:
    1. Major cultural red flags
    2. Work-life balance assessment
    3. Management quality indicators
    4. Overall recommendation
    """
```

## Implementation Flow
1. Receive company name from job listing
2. Execute scraping workflow
3. Clean and structure scraped data
4. Process through Gemini AI
5. Cache results (7-day TTL)
6. Present analyzed insights

## Error Handling
- Anti-scraping detection
- Failed page loads
- Incomplete data
- Rate limiting
- Gemini API failures

## Privacy & Legal
- Respect robots.txt
- Implement reasonable delays
- Store only processed insights
- Clear data retention policy
