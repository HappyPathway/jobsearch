from flask import Flask, request
import functions_framework
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
from generate_documents import generate_job_documents

@functions_framework.http
def generate_job_documents(request):
    """HTTP Cloud Function to generate tailored job application documents.
    
    Args:
        request (flask.Request): The request object
        {
            "job_info": {
                // Job details object with title, company, requirements, etc.
            },
            "use_writing_pass": true,  # optional
            "use_visual_resume": true,  # optional
            "send_slack": true  # optional
        }
    Returns:
        Generated document paths in GCS or error details
    """
    try:
        # Parse request data
        request_json = request.get_json(silent=True)
        if not request_json:
            return 'No request data provided', 400
            
        job_info = request_json.get('job_info')
        if not job_info:
            return 'job_info is required', 400
            
        # Get optional parameters
        use_writing_pass = request_json.get('use_writing_pass', True)
        use_visual_resume = request_json.get('use_visual_resume', True)
        send_slack = request_json.get('send_slack', True)
        
        # Generate documents
        resume_path, cover_letter_path = generate_job_documents(
            job_info,
            use_writing_pass=use_writing_pass,
            use_visual_resume=use_visual_resume,
            send_slack=send_slack
        )
        
        if resume_path and cover_letter_path:
            response = {
                'status': 'success',
                'documents': {
                    'resume': resume_path,
                    'cover_letter': cover_letter_path
                }
            }
            
            if use_visual_resume:
                response['documents'].update({
                    'visual_resume': str(Path(resume_path).parent / "resume_visual.pdf"),
                    'ats_resume': str(Path(resume_path).parent / "resume_ats.pdf")
                })
                
            return response
            
        return {
            'status': 'error',
            'message': 'Failed to generate documents'
        }, 500

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }, 500