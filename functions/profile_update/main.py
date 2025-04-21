from flask import Flask, request
import functions_framework
import sys
from pathlib import Path

# Add the scripts directory to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
from profile_scraper import extract_text_from_pdf, parse_profile_text, save_to_database
from resume_parser import parse_resume
from cover_letter_parser import parse_cover_letter
from combine_and_summarize import combine_profile_data

@functions_framework.http
def update_profile_data(request):
    """HTTP Cloud Function to update profile data.
    
    Args:
        request (flask.Request): The request object
        {
            "update_profile": true,  # optional
            "update_resume": true,   # optional
            "update_cover_letter": true,  # optional
            "combine_data": true     # optional
        }
    Returns:
        Status of the profile update operations
    """
    try:
        # Parse request data
        request_json = request.get_json(silent=True) or {}
        
        # Get parameters with defaults (all true if not specified)
        update_profile = request_json.get('update_profile', True)
        update_resume = request_json.get('update_resume', True)
        update_cover_letter = request_json.get('update_cover_letter', True)
        combine_data = request_json.get('combine_data', True)

        results = {
            'status': 'success',
            'operations': {}
        }

        # Process LinkedIn Profile
        if update_profile:
            try:
                pdf_path = Path(__file__).parent.parent.parent / 'inputs' / 'Profile.pdf'
                if pdf_path.exists():
                    profile_text = extract_text_from_pdf(pdf_path)
                    parsed_data = parse_profile_text(profile_text)
                    save_to_database(parsed_data)
                    results['operations']['profile'] = 'success'
                else:
                    results['operations']['profile'] = 'file_not_found'
            except Exception as e:
                results['operations']['profile'] = f'error: {str(e)}'

        # Process Resume
        if update_resume:
            try:
                resume_path = Path(__file__).parent.parent.parent / 'inputs' / 'Resume.pdf'
                if resume_path.exists():
                    parse_resume()
                    results['operations']['resume'] = 'success'
                else:
                    results['operations']['resume'] = 'file_not_found'
            except Exception as e:
                results['operations']['resume'] = f'error: {str(e)}'

        # Process Cover Letter
        if update_cover_letter:
            try:
                cover_letter_path = Path(__file__).parent.parent.parent / 'inputs' / 'CoverLetter.pdf'
                if cover_letter_path.exists():
                    parse_cover_letter()
                    results['operations']['cover_letter'] = 'success'
                else:
                    results['operations']['cover_letter'] = 'file_not_found'
            except Exception as e:
                results['operations']['cover_letter'] = f'error: {str(e)}'

        # Combine and Summarize
        if combine_data:
            try:
                combine_profile_data()
                results['operations']['combine_data'] = 'success'
            except Exception as e:
                results['operations']['combine_data'] = f'error: {str(e)}'

        # Check if any operation failed
        if any(isinstance(v, str) and v.startswith('error') for v in results['operations'].values()):
            results['status'] = 'partial_success'

        return results

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }, 500