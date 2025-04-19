#!/usr/bin/env python3
import os
import json
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from utils import session_scope
from models import RecruiterContact
from logging_utils import setup_logging

logger = setup_logging('recruiter_finder')

class RecruiterFinder:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        self.base_url = "https://www.linkedin.com/search/results/people/"
    
    def search_company_recruiters(self, company, limit=3, cache_only=False):
        """
        Search for recruiters at a specific company
        
        Args:
            company (str): Company name to search for recruiters
            limit (int): Maximum number of recruiters to return
            cache_only (bool): If True, only return recruiters from cache
            
        Returns:
            list: List of recruiter dictionaries with name, title, and URL
        """
        logger.info(f"Searching for recruiters at {company}")
        
        # First check if we have recruiters for this company in our database
        cached_recruiters = self.get_cached_recruiters(company)
        if cached_recruiters:
            logger.info(f"Found {len(cached_recruiters)} cached recruiters for {company}")
            return cached_recruiters[:limit]
            
        # If cache_only is True, return empty list if no cache hits
        if cache_only:
            logger.info(f"No cached recruiters found for {company} and cache_only is True")
            return []
        
        # Otherwise, search LinkedIn
        try:
            # Build search query for recruiters at the company
            query_params = {
                "keywords": f"{company} (recruiter OR \"talent acquisition\" OR \"technical recruiter\")",
                "origin": "GLOBAL_SEARCH_HEADER",
                "sortBy": "RELEVANCE"
            }
            
            response = requests.get(self.base_url, params=query_params, headers=self.headers)
            if response.status_code != 200:
                logger.error(f"Failed to search LinkedIn for recruiters at {company}: {response.status_code}")
                return []
                
            soup = BeautifulSoup(response.text, 'html.parser')
            search_results = soup.find_all("div", class_="entity-result")
            
            recruiters = []
            for result in search_results[:limit]:
                try:
                    name_elem = result.find("span", class_="entity-result__title-text")
                    title_elem = result.find("div", class_="entity-result__primary-subtitle")
                    link_elem = result.find("a", class_="app-aware-link")
                    
                    if name_elem and title_elem and link_elem:
                        name = name_elem.get_text(strip=True)
                        title = title_elem.get_text(strip=True)
                        url = link_elem.get("href").split("?")[0]  # Remove query parameters
                        
                        # Check if this appears to be a recruiter based on the title
                        if self._is_recruiter_title(title) and company.lower() in title.lower():
                            recruiter = {
                                "name": name,
                                "title": title,
                                "url": url
                            }
                            recruiters.append(recruiter)
                            
                            # Store in database for future use
                            self.store_recruiter(name, title, company, url)
                except Exception as e:
                    logger.error(f"Error parsing recruiter result: {str(e)}")
                    continue
            
            logger.info(f"Found {len(recruiters)} recruiters for {company}")
            # Add a sleep to avoid rate limiting
            time.sleep(random.uniform(1, 2))
            return recruiters
            
        except Exception as e:
            logger.error(f"Error searching for recruiters at {company}: {str(e)}")
            return []
    
    def _is_recruiter_title(self, title):
        """Check if a title matches common recruiter title patterns"""
        recruiter_keywords = [
            'recruit', 'talent', 'acquisition', 'hr', 'human resource', 
            'sourcing', 'sourcer', 'staffing', 'hiring'
        ]
        
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in recruiter_keywords)
    
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
                        source="linkedin",
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