from flask import Flask, request
import functions_framework
from datetime import datetime
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
from medium_publisher import MediumPublisher

@functions_framework.http
def generate_medium_article(request):
    """HTTP Cloud Function to generate and optionally publish a Medium article.
    
    Args:
        request (flask.Request): The request object
        {
            "skill": "optional skill to write about",
            "preview_only": true/false
        }
    Returns:
        The article URL or GCS path where the article was saved
    """
    try:
        # Parse request data
        request_json = request.get_json(silent=True)
        
        if request_json:
            skill = request_json.get('skill')
            preview_only = request_json.get('preview_only', False)
        else:
            skill = None
            preview_only = False

        # Initialize publisher
        medium = MediumPublisher()
        
        if preview_only:
            # Just generate and save to GCS
            selected_skill = skill or medium.select_skill_for_article()
            if not selected_skill:
                return 'No skill selected', 400
            
            article_data = medium.generate_article(selected_skill)
            if article_data:
                gcs_path = medium.save_article(article_data)
                if gcs_path:
                    return {
                        'status': 'success',
                        'message': 'Article generated in preview mode',
                        'path': gcs_path
                    }
            return 'Failed to generate article', 500
        else:
            # Generate and publish
            result = medium.generate_and_publish_article(skill)
            if result:
                return {
                    'status': 'success',
                    'message': 'Article generated and published',
                    'url': result
                }
            return 'Failed to complete article process', 500
            
    except Exception as e:
        return str(e), 500