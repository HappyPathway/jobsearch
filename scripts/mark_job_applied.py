import sqlite3
from datetime import datetime
import argparse
from pathlib import Path
from slugify import slugify
import json
import shutil
from utils import setup_logging

logger = setup_logging('mark_job_applied')

def find_job_directory(url):
    """Find the job directory based on the job URL"""
    applications_dir = Path(__file__).parent.parent / 'applications'
    if not applications_dir.exists():
        return None
        
    # Look for job_details.json files in subdirectories
    for job_dir in applications_dir.glob('**/job_details.json'):
        try:
            with open(job_dir) as f:
                details = json.load(f)
                if details.get('url') == url:
                    return job_dir.parent
        except Exception as e:
            logger.error(f"Error reading {job_dir}: {str(e)}")
            continue
    
    return None

def mark_job_applied(url, status='applied', notes=None):
    """Mark a job as applied in the database"""
    logger.info(f"Marking job as {status}: {url}")
    
    conn = sqlite3.connect('career_data.db')
    c = conn.cursor()
    
    try:
        # Get job details from cache
        c.execute("SELECT id FROM job_cache WHERE url = ?", (url,))
        job_row = c.fetchone()
        
        if not job_row:
            logger.error(f"Job not found in cache: {url}")
            return False
            
        job_id = job_row[0]
        application_date = datetime.now().strftime("%Y-%m-%d")
        
        # Record the application
        c.execute("""
            INSERT INTO job_applications (job_cache_id, application_date, status, notes)
            VALUES (?, ?, ?, ?)
        """, (job_id, application_date, status, notes))
        
        conn.commit()
        
        # Move job directory to applied directory if it exists
        job_dir = find_job_directory(url)
        if job_dir:
            applied_dir = Path(__file__).parent.parent / 'applications' / 'applied'
            applied_dir.mkdir(exist_ok=True)
            
            # Create a new directory name with the application date
            new_dir_name = f"{application_date}_{job_dir.name}"
            new_dir = applied_dir / new_dir_name
            
            # Move the directory
            shutil.move(str(job_dir), str(new_dir))
            logger.info(f"Moved job directory to {new_dir}")
        
        logger.info(f"Successfully marked job as {status}")
        return True
        
    except Exception as e:
        logger.error(f"Error marking job as applied: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Mark a job as applied')
    parser.add_argument('url', help='URL of the job listing')
    parser.add_argument('--status', default='applied', 
                      help='Application status (e.g., applied, interviewed, rejected)')
    parser.add_argument('--notes', help='Notes about the application')
    
    args = parser.parse_args()
    success = mark_job_applied(args.url, args.status, args.notes)
    
    if not success:
        exit(1)