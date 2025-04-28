import os
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import google.generativeai as genai
from dotenv import load_dotenv
from jobsearch.core.logging_utils import setup_logging

logger = setup_logging('techcrunch_scraper')

# Configure Google Generative AI
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")
genai.configure(api_key=GEMINI_API_KEY)

class TechCrunchScraper:
    """Class to scrape and analyze TechCrunch articles"""

    def __init__(self):
        self.base_url = "https://techcrunch.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def search_company(self, company_name):
        """Search for recent articles about a company"""
        try:
            search_url = f"{self.base_url}/search/{company_name}"
            response = requests.get(search_url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Error searching TechCrunch for {company_name}: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            articles = []
            
            # Get articles from last 6 months
            cutoff_date = datetime.now() - timedelta(days=180)
            
            # Find article blocks
            for article in soup.find_all('article', class_='post-block'):
                try:
                    title = article.find('h2').text.strip()
                    date_str = article.find('time').get('datetime')
                    date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    url = article.find('h2').find('a')['href']
                    excerpt = article.find('div', class_='post-block__content').text.strip()
                    
                    if date >= cutoff_date:
                        articles.append({
                            'title': title,
                            'date': date,
                            'url': url,
                            'excerpt': excerpt
                        })
                except Exception as e:
                    logger.warning(f"Error parsing article for {company_name}: {str(e)}")
                    continue
            
            return articles[:5]  # Return up to 5 most recent articles
            
        except Exception as e:
            logger.error(f"Error in TechCrunch search for {company_name}: {str(e)}")
            return None

    def get_article_content(self, url):
        """Get the full content of an article"""
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Error fetching article content: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            article_body = soup.find('div', class_='article-content')
            
            if not article_body:
                return None
                
            paragraphs = []
            for p in article_body.find_all('p'):
                text = p.text.strip()
                if text and not any(x in text.lower() for x in ['advertisement', 'sponsored']):
                    paragraphs.append(text)
                    
            return '\n\n'.join(paragraphs)
            
        except Exception as e:
            logger.error(f"Error getting article content: {str(e)}")
            return None

    def analyze_company_coverage(self, company_name, articles):
        """Analyze recent TechCrunch coverage of a company using Gemini"""
        try:
            if not articles:
                return {
                    'error': 'No recent articles found',
                    'news_sentiment': 'neutral',
                    'key_developments': [],
                    'market_position': 'unknown',
                    'growth_trajectory': 'unknown',
                    'recommendation': 'Insufficient recent news coverage to make an assessment.'
                }

            # Combine article excerpts for analysis
            coverage_text = "\n\n".join([
                f"Article: {article['title']}\nDate: {article['date']}\nExcerpt: {article['excerpt']}"
                for article in articles
            ])

            prompt = f"""Analyze recent TechCrunch coverage of {company_name} and provide insights about the company's current state and trajectory.

Recent Coverage:
{coverage_text}

Provide a structured analysis with:
1. Overall news sentiment (positive/negative/neutral)
2. Key company developments
3. Market position assessment
4. Growth trajectory
5. Recommendation for job seekers

Focus on factual insights that would be relevant for someone considering employment at the company."""

            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt)
            
            # Parse the response to extract structured insights
            content = response.text
            
            analysis = {
                'news_sentiment': 'neutral',  # Default values
                'key_developments': [],
                'market_position': 'unknown',
                'growth_trajectory': 'unknown',
                'recommendation': ''
            }

            # Extract sentiment
            sentiment_indicators = {
                'positive': ['positive', 'favorable', 'strong', 'growing', 'successful'],
                'negative': ['negative', 'concerning', 'struggling', 'declining', 'troubled'],
                'neutral': ['neutral', 'mixed', 'stable', 'steady']
            }
            
            for sentiment, indicators in sentiment_indicators.items():
                if any(indicator in content.lower() for indicator in indicators):
                    analysis['news_sentiment'] = sentiment
                    break

            # Extract key developments
            developments_section = content.split('developments')[1].split('\n') if 'developments' in content.lower() else []
            analysis['key_developments'] = [d.strip('- ') for d in developments_section if d.strip().startswith('-')][:3]

            # Extract market position
            if 'market position' in content.lower():
                position_section = content.split('market position')[1].split('\n')[0]
                analysis['market_position'] = position_section.strip('.: ')

            # Extract growth trajectory
            if 'growth' in content.lower():
                growth_section = content.split('growth')[1].split('\n')[0]
                analysis['growth_trajectory'] = growth_section.strip('.: ')

            # Extract recommendation
            if 'recommendation' in content.lower():
                rec_section = content.split('recommendation')[1].split('\n')[0]
                analysis['recommendation'] = rec_section.strip('.: ')

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing company coverage: {str(e)}")
            return {
                'error': str(e),
                'news_sentiment': 'neutral',
                'key_developments': [],
                'market_position': 'unknown',
                'growth_trajectory': 'unknown',
                'recommendation': 'Error analyzing news coverage.'
            }