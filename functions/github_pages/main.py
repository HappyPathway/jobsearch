from flask import Flask, request
import functions_framework
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
from generate_github_pages import generate_pages

@functions_framework.http
def deploy_github_pages(request):
    """HTTP Cloud Function to generate and deploy GitHub Pages content.
    
    Args:
        request (flask.Request): The request object
        {
            // No parameters needed, but could add customization options in the future
        }
    Returns:
        Status of the GitHub Pages generation and deployment
    """
    try:
        if generate_pages():
            return {
                'status': 'success',
                'message': 'GitHub Pages content generated and stored in GCS'
            }
        else:
            return {
                'status': 'error',
                'message': 'Failed to generate GitHub Pages content'
            }, 500
            
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }, 500