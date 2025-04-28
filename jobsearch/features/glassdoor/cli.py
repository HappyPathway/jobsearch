#!/usr/bin/env python3
"""Command-line interface for Glassdoor company analysis."""

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Dict

from jobsearch.core.logging import setup_logging
from .scraper import GlassdoorScraper
from .analyzer import GlassdoorAnalyzer

logger = setup_logging('glassdoor_cli')

def analyze_company(company_name: str, api_key: str = None) -> Dict:
    """Analyze a company using Glassdoor data."""
    if not api_key:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("Gemini API key not provided and GEMINI_API_KEY env var not set")
    
    try:
        # Scrape company data
        with GlassdoorScraper() as scraper:
            company_url = scraper.search_company(company_name)
            if not company_url:
                logger.error(f"Could not find Glassdoor page for {company_name}")
                return {'error': 'Company not found'}
            
            company_data = scraper.get_company_data(company_url)
            if not company_data:
                logger.error(f"Failed to get data for {company_name}")
                return {'error': 'Failed to get company data'}
        
        # Analyze the data
        analyzer = GlassdoorAnalyzer(api_key)
        analysis = analyzer.analyze_company(company_name, company_data)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing company {company_name}: {e}")
        return {'error': str(e)}

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description='Analyze companies using Glassdoor data')
    parser.add_argument('company_name', help='Name of the company to analyze')
    parser.add_argument('--api-key', help='Gemini API key (or set GEMINI_API_KEY env var)')
    parser.add_argument('--output', help='Output file path (default: print to stdout)')
    
    args = parser.parse_args()
    
    try:
        analysis = analyze_company(args.company_name, args.api_key)
        
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(json.dumps(analysis, indent=2))
            print(f"Analysis written to {args.output}")
        else:
            print(json.dumps(analysis, indent=2))
            
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()