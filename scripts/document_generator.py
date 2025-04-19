import os
from logging_utils import setup_logging
import generate_documents

logger = setup_logging('document_generator')

def generate_documents_for_jobs(job_searches, filter_priority="high"):
    """Generate tailored documents for jobs based on priority filter
    
    Args:
        job_searches (list): List of job search results
        filter_priority (str): Priority level to filter jobs by ('high', 'medium', 'low', or None for all)
        
    Returns:
        list: List of generated documents info
    """
    logger.info(f"Generating tailored documents for {filter_priority} priority jobs")
    try:
        generated_docs = []
        for search in job_searches:
            for job in search['listings']:
                # Only generate documents for jobs matching priority filter
                if not filter_priority or job.get('application_priority', '').lower() == filter_priority.lower():
                    logger.info(f"Generating documents for {job['title']} at {job['company']}")
                    resume_path, cover_letter_path = generate_documents.generate_job_documents(job)
                    if resume_path and cover_letter_path:
                        generated_docs.append({
                            "job": job,
                            "resume": resume_path,
                            "cover_letter": cover_letter_path
                        })
        return generated_docs
    except Exception as e:
        logger.error(f"Failed to generate documents: {str(e)}")
        return []

if __name__ == "__main__":
    # Example usage
    import sys
    from pathlib import Path
    import json
    
    # Load a job from file if provided
    if len(sys.argv) > 1:
        job_file = sys.argv[1]
        with open(job_file, 'r') as f:
            job_data = json.load(f)
            
        job_searches = [{'role': 'Test', 'listings': [job_data]}]
        docs = generate_documents_for_jobs(job_searches, filter_priority=None)
        
        if docs:
            print(f"Generated documents: {docs}")
        else:
            print("No documents were generated")