"""Glassdoor web scraping implementation."""

from typing import Dict, List, Optional
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time
import json

from jobsearch.core.logging import setup_logging

logger = setup_logging('glassdoor_scraper')

class GlassdoorScraper:
    """Handles web scraping of Glassdoor company data."""
    
    def __init__(self):
        self.base_url = "https://www.glassdoor.com"
        self._setup_browser()
    
    def _setup_browser(self):
        """Initialize the Playwright browser."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up browser resources."""
        if hasattr(self, 'context'):
            self.context.close()
        if hasattr(self, 'browser'):
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
    
    def search_company(self, company_name: str) -> Optional[str]:
        """Search for a company and return its Glassdoor URL."""
        try:
            page = self.context.new_page()
            search_url = f"{self.base_url}/Search/results.htm?keyword={company_name}"
            page.goto(search_url)
            page.wait_for_load_state('networkidle')
            
            # Find company link in search results
            company_link = page.get_by_role("link", name=company_name, exact=True)
            if company_link:
                return company_link.get_attribute('href')
            return None
            
        except Exception as e:
            logger.error(f"Error searching for company {company_name}: {e}")
            return None
        finally:
            page.close()
    
    def get_company_data(self, company_url: str) -> Dict:
        """Scrape company data from Glassdoor."""
        try:
            page = self.context.new_page()
            page.goto(company_url)
            page.wait_for_load_state('networkidle')
            
            data = {
                'ratings': self._get_ratings(page),
                'reviews': self._get_reviews(page),
                'culture': self._get_culture_ratings(page)
            }
            
            return data
            
        except Exception as e:
            logger.error(f"Error getting company data from {company_url}: {e}")
            return {}
        finally:
            page.close()
    
    def _get_ratings(self, page) -> Dict[str, float]:
        """Extract company ratings."""
        ratings = {}
        rating_elements = page.query_selector_all('[data-test="rating-info"]')
        
        for elem in rating_elements:
            category = elem.get_attribute('data-category')
            value = elem.inner_text()
            try:
                ratings[category] = float(value)
            except ValueError:
                continue
                
        return ratings
    
    def _get_reviews(self, page) -> List[Dict]:
        """Extract recent reviews."""
        reviews = []
        review_elements = page.query_selector_all('[data-test="employer-review"]')
        
        for elem in review_elements[:20]:  # Get most recent 20 reviews
            review = {
                'title': elem.query_selector('.review-title').inner_text(),
                'pros': elem.query_selector('.pros').inner_text(),
                'cons': elem.query_selector('.cons').inner_text(),
                'rating': float(elem.query_selector('.rating').get_attribute('data-rating')),
                'date': elem.query_selector('.review-date').inner_text()
            }
            reviews.append(review)
            
        return reviews
    
    def _get_culture_ratings(self, page) -> Dict[str, float]:
        """Extract culture and values ratings."""
        culture = {}
        culture_elements = page.query_selector_all('[data-test="culture-value-rating"]')
        
        for elem in culture_elements:
            category = elem.get_attribute('data-category')
            value = elem.inner_text()
            try:
                culture[category] = float(value)
            except ValueError:
                continue
                
        return culture