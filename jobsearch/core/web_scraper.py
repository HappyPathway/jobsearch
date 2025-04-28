"""Generic web scraping utilities with rate limiting and caching."""

import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union, List
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from cachetools import TTLCache
from jobsearch.core.logging import setup_logging

logger = setup_logging('web_scraper')

class WebScraper:
    """Generic web scraping utility with built-in rate limiting and caching."""
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    def __init__(
        self,
        rate_limit: float = 1.0,  # Minimum seconds between requests
        max_retries: int = 3,
        cache_ttl: int = 3600,  # Cache TTL in seconds
        cache_size: int = 1000,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
    ):
        """Initialize web scraper with configuration.
        
        Args:
            rate_limit: Minimum time between requests in seconds
            max_retries: Maximum number of retry attempts for failed requests
            cache_ttl: Time-to-live for cached responses in seconds
            cache_size: Maximum number of cached responses
            headers: Optional custom headers to use for requests
            timeout: Request timeout in seconds
        """
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.timeout = timeout
        self.headers = headers or self.DEFAULT_HEADERS.copy()
        
        # Set up caching
        self.cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)
        
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)

    def _wait_for_rate_limit(self):
        """Ensure minimum time between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit:
            sleep_time = self.rate_limit - time_since_last
            # Add small random jitter
            sleep_time += random.uniform(0, 0.5)
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def get(
        self, 
        url: str, 
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        **kwargs
    ) -> Optional[requests.Response]:
        """Make a GET request with rate limiting and caching.
        
        Args:
            url: URL to request
            params: Optional query parameters
            use_cache: Whether to use cached response if available
            **kwargs: Additional arguments passed to requests.get()
            
        Returns:
            Response object or None if request failed
        """
        # Generate cache key from URL and params
        cache_key = f"{url}:{str(params)}"
        
        # Check cache first
        if use_cache and cache_key in self.cache:
            logger.debug(f"Cache hit for {url}")
            return self.cache[cache_key]
            
        try:
            self._wait_for_rate_limit()
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            
            # Cache successful response
            if use_cache:
                self.cache[cache_key] = response
                
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def get_soup(
        self, 
        url: str, 
        params: Optional[Dict[str, Any]] = None,
        parser: str = 'html.parser',
        use_cache: bool = True,
        **kwargs
    ) -> Optional[BeautifulSoup]:
        """Make a GET request and parse response with BeautifulSoup.
        
        Args:
            url: URL to request
            params: Optional query parameters
            parser: BeautifulSoup parser to use
            use_cache: Whether to use cached response
            **kwargs: Additional arguments passed to requests.get()
            
        Returns:
            BeautifulSoup object or None if request failed
        """
        response = self.get(url, params, use_cache, **kwargs)
        if response is None:
            return None
            
        try:
            return BeautifulSoup(response.text, parser)
        except Exception as e:
            logger.error(f"Error parsing response from {url}: {str(e)}")
            return None

    def extract_text(
        self,
        element: BeautifulSoup,
        selector: str,
        attribute: Optional[str] = None,
        default: str = ""
    ) -> str:
        """Safely extract text or attribute from a BeautifulSoup element.
        
        Args:
            element: BeautifulSoup element to search within
            selector: CSS selector to find element
            attribute: Optional attribute to extract instead of text
            default: Default value if element or attribute not found
            
        Returns:
            Extracted text or attribute value
        """
        try:
            found = element.select_one(selector)
            if found:
                if attribute:
                    return found.get(attribute, default)
                return found.get_text(strip=True)
            return default
        except Exception as e:
            logger.error(f"Error extracting {selector}: {str(e)}")
            return default

    def extract_all_text(
        self,
        element: BeautifulSoup,
        selector: str,
        attribute: Optional[str] = None
    ) -> List[str]:
        """Safely extract text or attributes from multiple matching elements.
        
        Args:
            element: BeautifulSoup element to search within
            selector: CSS selector to find elements
            attribute: Optional attribute to extract instead of text
            
        Returns:
            List of extracted text or attribute values
        """
        try:
            elements = element.select(selector)
            if attribute:
                return [el.get(attribute, "").strip() for el in elements if el.get(attribute)]
            return [el.get_text(strip=True) for el in elements if el.get_text(strip=True)]
        except Exception as e:
            logger.error(f"Error extracting {selector}: {str(e)}")
            return []

    def clear_cache(self):
        """Clear the response cache."""
        self.cache.clear()
