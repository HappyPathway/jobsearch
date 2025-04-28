"""Tests for Glassdoor company analysis feature."""

import pytest
from unittest.mock import Mock, patch
from jobsearch.features.glassdoor.scraper import GlassdoorScraper
from jobsearch.features.glassdoor.analyzer import GlassdoorAnalyzer

@pytest.fixture
def mock_scraper():
    """Mock Glassdoor scraper for testing."""
    with patch('playwright.sync_api.sync_playwright') as mock_playwright:
        scraper = GlassdoorScraper()
        yield scraper

@pytest.fixture
def mock_analyzer():
    """Mock Glassdoor analyzer for testing."""
    with patch('google.generativeai.GenerativeModel') as mock_model:
        analyzer = GlassdoorAnalyzer('fake-api-key')
        yield analyzer

def test_scraper_initialization(mock_scraper):
    """Test that the scraper can be initialized."""
    assert isinstance(mock_scraper, GlassdoorScraper)

def test_analyzer_initialization(mock_analyzer):
    """Test that the analyzer can be initialized."""
    assert isinstance(mock_analyzer, GlassdoorAnalyzer)
    assert mock_analyzer.api_key == 'fake-api-key'