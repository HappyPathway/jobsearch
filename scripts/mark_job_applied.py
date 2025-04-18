import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from logging_utils import setup_logging
from models import Session, JobCache, JobApplication

logger = setup_logging('mark_job_applied')

def mark_job_as_applied(url, status='applied', notes=None):
    """Mark a job as applied in the database"""
    session = Session()
    try:
        # Find the job in the cache
        job = session.query(JobCache).filter_by(url=url).first()
        if not job:
            logger.error(f"Job not found in cache: {url}")
            return False
        
        # Create application record
        application = JobApplication(
            job_cache_id=job.id,
            application_date=datetime.now().strftime("%Y-%m-%d"),
            status=status,
            notes=notes or '',
            resume_path='',  # Will be updated when documents are generated
            cover_letter_path=''  # Will be updated when documents are generated
        )
        
        session.add(application)
        session.commit()
        
        logger.info(f"Successfully marked job as applied: {job.title} at {job.company}")
        return True
        
    except Exception as e:
        logger.error(f"Error marking job as applied: {str(e)}")
        session.rollback()
        return False
    finally:
        session.close()

def main():
    parser = argparse.ArgumentParser(description='Mark a job as applied')
    parser.add_argument('url', help='URL of the job posting')
    parser.add_argument('--status', default='applied',
                    help='Application status (default: applied)')
    parser.add_argument('--notes', help='Additional notes about the application')
    
    args = parser.parse_args()
    
    if mark_job_as_applied(args.url, args.status, args.notes):
        print(f"Successfully marked job as {args.status}")
    else:
        print("Failed to mark job as applied")
        exit(1)

if __name__ == "__main__":
    main()