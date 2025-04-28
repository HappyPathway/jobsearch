"""Tests for web scraping utilities."""

import pytest
from unittest.mock import Mock, patch
import requests
from bs4 import BeautifulSoup
from jobsearch.core.web_scraper import WebScraper

@pytest.fixture
def scraper():
    """Create a WebScraper instance for testing."""
    return WebScraper(rate_limit=0)  # No rate limiting in tests

def test_headers_configuration():
    """Test custom headers configuration."""
    custom_headers = {"User-Agent": "Custom Agent"}
    scraper = WebScraper(headers=custom_headers)
    assert scraper.headers["User-Agent"] == "Custom Agent"
    # Should merge with default headers
    assert "Accept" in scraper.headers

@pytest.mark.vcr()
def test_get_request_success(scraper):
    """Test successful GET request."""
    response = scraper.get("https://httpbin.org/get")
    assert response is not None
    assert response.status_code == 200

@pytest.mark.vcr()
def test_get_request_failure(scraper):
    """Test failed GET request."""
    response = scraper.get("https://httpbin.org/status/404")
    assert response is None

def test_caching(scraper):
    """Test response caching."""
    with patch('requests.Session.get') as mock_get:
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # First request should hit the network
        scraper.get("https://example.com", use_cache=True)
        assert mock_get.call_count == 1
        
        # Second request should use cache
        scraper.get("https://example.com", use_cache=True)
        assert mock_get.call_count == 1

def test_rate_limiting():
    """Test rate limiting between requests."""
    import time
    
    scraper = WebScraper(rate_limit=1.0)
    start_time = time.time()
    
    with patch('requests.Session.get') as mock_get:
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Make two requests
        scraper.get("https://example.com")
        scraper.get("https://example.com")
        
        # Should have waited at least rate_limit seconds
        elapsed = time.time() - start_time
        assert elapsed >= 1.0

def test_soup_parsing(scraper):
    """Test BeautifulSoup parsing of response."""
    html = "<html><body><h1>Test</h1></body></html>"
    with patch('requests.Session.get') as mock_get:
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = html
        mock_get.return_value = mock_response
        
        soup = scraper.get_soup("https://example.com")
        assert soup is not None
        assert soup.h1.text == "Test"

def test_text_extraction(scraper):
    """Test text extraction helpers."""
    html = """
    <div class="content">
        <h1 class="title">Title</h1>
        <p class="text">Paragraph 1</p>
        <p class="text">Paragraph 2</p>
        <a href="https://example.com">Link</a>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Test single element extraction
    assert scraper.extract_text(soup, ".title") == "Title"
    assert scraper.extract_text(soup, "a", attribute="href") == "https://example.com"
    assert scraper.extract_text(soup, ".missing", default="Not Found") == "Not Found"
    
    # Test multiple elements extraction
    texts = scraper.extract_all_text(soup, ".text")
    assert len(texts) == 2
    assert texts == ["Paragraph 1", "Paragraph 2"]
