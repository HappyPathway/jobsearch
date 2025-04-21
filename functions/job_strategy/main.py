from flask import Flask, request
import functions_framework
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
from job_strategy import (
    get_target_roles_from_profile,
    search_jobs,
    generate_and_save_strategy,
    generate_documents_for_jobs,
    generate_medium_article
)

@functions_framework.http
def generate_job_strategy(request):
    """HTTP Cloud Function to generate job search strategy.
    
    Args:
        request (flask.Request): The request object
        {
            "job_limit": 5,  # optional, number of jobs per search query
            "include_recruiters": false,  # optional
            "generate_documents": false,  # optional
            "generate_article": false,  # optional
            "preview_article": false,  # optional
            "send_slack": true  # optional
        }
    Returns:
        The strategy file paths and any additional generated content
    """
    try:
        # Parse request data
        request_json = request.get_json(silent=True) or {}
        
        # Get parameters with defaults
        job_limit = request_json.get('job_limit', 5)
        include_recruiters = request_json.get('include_recruiters', False)
        generate_docs = request_json.get('generate_documents', False)
        generate_article = request_json.get('generate_article', False)
        preview_article = request_json.get('preview_article', False)
        send_slack = request_json.get('send_slack', True)

        # Get target roles from profile
        search_queries = get_target_roles_from_profile()
        
        # Search for jobs
        job_searches = search_jobs(search_queries, job_limit)
        if not job_searches:
            return 'No jobs found', 404

        # Generate strategy
        strategy, md_path, txt_path = generate_and_save_strategy(
            job_searches,
            None,  # output_dir not needed for GCS storage
            send_slack,
            include_recruiters
        )

        response = {
            'status': 'success',
            'strategy_files': {
                'markdown': md_path,
                'text': txt_path
            }
        }

        # Generate documents if requested
        if generate_docs:
            generated_docs = generate_documents_for_jobs(job_searches, filter_priority="high")
            response['generated_documents'] = generated_docs

        # Generate Medium article if requested
        if generate_article or preview_article:
            article_result = generate_medium_article(strategy, preview_only=preview_article)
            if article_result:
                response['article'] = article_result

        return response

    except Exception as e:
        return str(e), 500