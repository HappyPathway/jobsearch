#!/usr/bin/env python3
"""Command-line tool for analyzing job postings."""

import sys
import json
from pathlib import Path
from jobsearch.scripts.job_analysis import analyze_jobs_batch
from jobsearch.scripts.common import JobInfo
from jobsearch.core.logging import setup_logging

logger = setup_logging('analyze_jobs')

def main():
    try:
        # Check if job file provided
        if len(sys.argv) < 2:
            print("Usage: analyze_jobs.py <job_file.json>")
            sys.exit(1)
            
        # Load job data
        job_file = Path(sys.argv[1])
        if not job_file.exists():
            logger.error(f"Job file not found: {job_file}")
            sys.exit(1)
            
        with open(job_file) as f:
            job_data = json.load(f)
            
        # Convert to JobInfo objects
        jobs = []
        for job in job_data:
            jobs.append(JobInfo(
                url=job['url'],
                title=job['title'],
                company=job['company'],
                description=job['description'],
                location=job.get('location', ''),
                post_date=job.get('post_date')
            ))
            
        # Analyze jobs
        results = analyze_jobs_batch(jobs)
        
        # Output results
        print(json.dumps(results, indent=2))
        return 0
            
    except Exception as e:
        logger.error(f"Error analyzing jobs: {str(e)}")
        return 1
        
if __name__ == "__main__":
    sys.exit(main())