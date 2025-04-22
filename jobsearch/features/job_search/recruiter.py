#!/usr/bin/env python3
import os
import json
from datetime import datetime
from utils import session_scope
from models import RecruiterContact
from logging_utils import setup_logging
import google.generativeai as genai
from dotenv import load_dotenv

logger = setup_logging('recruiter_finder')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class RecruiterFinder:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        self.base_url = "https://www.linkedin.com/search/results/people/"
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    def search_company_recruiters(self, company, limit=3, cache_only=False):
        """Search for recruiters at a specific company"""
        logger.info(f"Searching for recruiters at {company}")
        
        # First check cache
        cached_recruiters = self.get_cached_recruiters(company)
        if cached_recruiters:
            logger.info(f"Found {len(cached_recruiters)} cached recruiters for {company}")
            return cached_recruiters[:limit]
            
        if cache_only:
            logger.info(f"No cached recruiters found for {company} and cache_only is True")
            return []
        
        # Search LinkedIn
        try:
            # Build search query for recruiters at the company
            query_params = {
                "keywords": f"{company} (recruiter OR \"talent acquisition\" OR \"technical recruiter\")",
                "origin": "GLOBAL_SEARCH_HEADER",
                "sortBy": "RELEVANCE"
            }
            
            import requests
            response = requests.get(self.base_url, params=query_params, headers=self.headers)
            if response.status_code != 200:
                logger.error(f"Failed to search LinkedIn for recruiters at {company}: {response.status_code}")
                return []
            
            # Get the raw HTML and send it to Gemini for parsing
            html_content = response.text
            
            prompt = f"""Extract recruiter information from this LinkedIn search results HTML. Focus on finding technical recruiters or talent acquisition specialists for {company}.

The HTML content is:
{html_content}

Required JSON format:
{{
    "recruiters": [
        {{
            "name": "Full name of recruiter",
            "title": "Current recruiting title",
            "url": "LinkedIn profile URL",
            "status": "identified"
        }}
    ]
}}

Rules:
1. Only include recruiters currently at {company}
2. Look for technical recruiting or talent acquisition roles
3. Extract the exact LinkedIn profile URL if present
4. Limit to {limit} most relevant results
5. If no URL is found, create a plausible one based on name"""

            response = self.model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": 2000,
                    "temperature": 0.1,
                }
            )

            # Clean and parse the response
            response_text = response.text.strip()
            # Remove any markdown code block indicators
            response_text = response_text.replace('```json\n', '').replace('\n```', '')
            try:
                data = json.loads(response_text)
                recruiters = data.get('recruiters', [])
            except json.JSONDecodeError:
                logger.error("Failed to parse Gemini response as JSON")
                return []
            
            # Store recruiter profiles in database
            for recruiter in recruiters:
                self.store_recruiter(
                    recruiter['name'],
                    recruiter['title'],
                    company,
                    recruiter['url']
                )
            
            logger.info(f"Found {len(recruiters)} recruiter profiles for {company}")
            return recruiters[:limit]
            
        except Exception as e:
            logger.error(f"Error searching for recruiters at {company}: {str(e)}")
            return []

    def get_cached_recruiters(self, company):
        """Get recruiters for a company from the database"""
        try:
            with session_scope() as session:
                recruiters = session.query(RecruiterContact).filter(RecruiterContact.company.ilike(f"%{company}%")).all()
                
                return [
                    {
                        "name": recruiter.name,
                        "title": recruiter.title,
                        "url": recruiter.url,
                        "status": recruiter.status
                    }
                    for recruiter in recruiters
                ]
        except Exception as e:
            logger.error(f"Error retrieving cached recruiters: {str(e)}")
            return []

    def store_recruiter(self, name, title, company, url):
        """Store a recruiter in the database"""
        try:
            with session_scope() as session:
                # Check if recruiter already exists
                existing = session.query(RecruiterContact).filter_by(url=url).first()
                if not existing:
                    recruiter = RecruiterContact(
                        name=name,
                        title=title,
                        company=company,
                        url=url,
                        source="gemini",
                        found_date=datetime.now().isoformat(),
                        status="identified"
                    )
                    session.add(recruiter)
                    logger.info(f"Stored new recruiter: {name} at {company}")
                else:
                    logger.debug(f"Recruiter already exists: {name} at {company}")
        except Exception as e:
            logger.error(f"Error storing recruiter: {str(e)}")

# Global instance
_recruiter_finder = None

def get_recruiter_finder():
    """Get a singleton instance of the RecruiterFinder"""
    global _recruiter_finder
    if _recruiter_finder is None:
        _recruiter_finder = RecruiterFinder()
    return _recruiter_finder