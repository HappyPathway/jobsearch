import os
import sys
import argparse
from datetime import datetime
from pathlib import Path
from jobsearch.core.logging import setup_logging
from models import Session, JobCache, JobApplication
from dotenv import load_dotenv

# Import Slack notifier
try:
    from slack_notifier import get_notifier
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

logger = setup_logging('mark_job_applied')
load_dotenv()

# Check if Slack notifications are enabled by default
DEFAULT_SLACK_NOTIFICATIONS = os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false").lower() in ["true", "1", "yes"]

def mark_job_as_applied(url, status='applied', notes=None, send_slack=DEFAULT_SLACK_NOTIFICATIONS):
    """Mark a job as applied in the database"""
    session = Session()
    try:
        # Find the job in the cache
        job = session.query(JobCache).filter_by(url=url).first()
        if not job:
            logger.error(f"Job not found in cache: {url}")
            return False
        
        # Check if application record exists
        application = session.query(JobApplication).filter_by(job_cache_id=job.id).first()
        old_status = None
        
        if application:
            # Update existing application
            old_status = application.status
            application.status = status
            if notes:
                if application.notes:
                    application.notes += f"\n\n{datetime.now().strftime('%Y-%m-%d %H:%M')}: {notes}"
                else:
                    application.notes = notes
        else:
            # Create new application record
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
        
        logger.info(f"Successfully marked job as {status}: {job.title} at {job.company}")
        
        # Send Slack notification if enabled
        if send_slack and SLACK_AVAILABLE and (not old_status or old_status != status):
            try:
                notifier = get_notifier()
                notifier.send_application_status_update(application, old_status)
                logger.info(f"Sent Slack notification about status change to {status}")
            except Exception as e:
                logger.error(f"Error sending Slack notification: {str(e)}")
        
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
    parser.add_argument('--no-slack', action='store_false', dest='send_slack',
                      help='Disable Slack notifications')
    parser.set_defaults(send_slack=DEFAULT_SLACK_NOTIFICATIONS)
    
    args = parser.parse_args()
    
    if mark_job_as_applied(args.url, args.status, args.notes, args.send_slack):
        print(f"Successfully marked job as {args.status}")
    else:
        print("Failed to mark job as applied")
        exit(1)

if __name__ == "__main__":
    main()