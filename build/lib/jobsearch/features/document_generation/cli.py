#!/usr/bin/env python3
"""Command-line tool for generating application documents."""

import sys
import json
from pathlib import Path
from jobsearch.scripts.document_generator import generate_documents_for_job
from jobsearch.scripts.common import JobInfo
from jobsearch.core.logging import setup_logging

logger = setup_logging('generate_docs')

def main():
    try:
        # Check if job file provided
        if len(sys.argv) < 2:
            print("Usage: generate_docs.py <job_file.json>")
            sys.exit(1)
            
        # Load job data
        job_file = Path(sys.argv[1])
        if not job_file.exists():
            logger.error(f"Job file not found: {job_file}")
            sys.exit(1)
            
        with open(job_file) as f:
            job_data = json.load(f)
            
        # Convert to JobInfo object
        job = JobInfo(
            url=job_data['url'],
            title=job_data['title'],
            company=job_data['company'],
            description=job_data['description'],
            location=job_data.get('location', ''),
            post_date=job_data.get('post_date')
        )
            
        # Generate documents
        result = generate_documents_for_job(job)
        
        # Output results
        if result['success']:
            print("✅ Documents generated successfully:")
            print(f"Resume: {result['resume']}")
            print(f"Cover Letter: {result['cover_letter']}")
            return 0
        else:
            print(f"❌ Error generating documents: {result['error']}")
            return 1
            
    except Exception as e:
        logger.error(f"Error generating documents: {str(e)}")
        return 1
        
if __name__ == "__main__":
    sys.exit(main())