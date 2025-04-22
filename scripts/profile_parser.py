import pdfplumber
import json
import re
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
from logging_utils import setup_logging
import tempfile
from datetime import datetime
from gcs_utils import gcs
from structured_prompt import StructuredPrompt

logger = setup_logging('profile_parser')

# Configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_profile_with_gemini(text):
    """Use Gemini to extract structured profile information from resume text"""
    try:
        # Initialize StructuredPrompt
        structured_prompt = StructuredPrompt()

        # Define expected structure
        expected_structure = {
            "contact_info": {
                "name": str,
                "email": str,
                "phone": str,
                "location": str,
                "linkedin": str
            },
            "core_skills": {
                "infrastructure_and_cloud": [{
                    "name": str,
                    "proficiency": str,
                    "years": int
                }],
                "development_and_automation": [{
                    "name": str,
                    "proficiency": str,
                    "years": int
                }],
                "platforms_and_tools": [{
                    "name": str,
                    "proficiency": str,
                    "years": int
                }],
                "methodologies": [{
                    "name": str,
                    "proficiency": str,
                    "years": int
                }]
            },
            "experience": [{
                "company": str,
                "title": str,
                "start_date": str,
                "end_date": str,
                "description": str,
                "achievements": [str],
                "technologies": [str]
            }],
            "education": [{
                "school": str,
                "degree": str,
                "field": str,
                "graduation_date": str
            }]
        }

        # Example data
        example_data = {
            "contact_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "(555) 123-4567",
                "location": "San Francisco, CA",
                "linkedin": "linkedin.com/in/johndoe"
            },
            "core_skills": {
                "infrastructure_and_cloud": [
                    {"name": "AWS", "proficiency": "expert", "years": 5}
                ],
                "development_and_automation": [
                    {"name": "Python", "proficiency": "expert", "years": 8}
                ],
                "platforms_and_tools": [
                    {"name": "Kubernetes", "proficiency": "advanced", "years": 3}
                ],
                "methodologies": [
                    {"name": "DevOps", "proficiency": "expert", "years": 5}
                ]
            },
            "experience": [{
                "company": "Tech Corp",
                "title": "Senior Cloud Architect",
                "start_date": "2020-01",
                "end_date": "Present",
                "description": "Led cloud transformation initiatives",
                "achievements": ["Reduced costs by 40%"],
                "technologies": ["AWS", "Terraform", "Kubernetes"]
            }],
            "education": [{
                "school": "University of Example",
                "degree": "Bachelor of Science",
                "field": "Computer Science",
                "graduation_date": "2010-05"
            }]
        }

        # Get structured response
        profile = structured_prompt.get_structured_response(
            prompt=f"""Extract structured profile information from this resume text.
Focus on organizing skills into appropriate categories and capturing all relevant details.

Profile text to parse:
{text}""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if not profile:
            logger.error("Failed to extract profile information")
            return None

        # Store in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(profile, temp_file, indent=2)

        # Upload to GCS
        gcs_path = 'parsed/profile.json'
        gcs.upload_file(temp_path, gcs_path)

        # Clean up temp file
        temp_path.unlink()

        return profile

    except Exception as e:
        logger.error(f"Error extracting profile information: {str(e)}")
        return None

def create_profile_json():
    """Create JSON profile from resume and store in GCS"""
    try:
        # Read resume from docs directory
        docs_dir = Path(__file__).parent.parent / 'inputs'
        resume_path = docs_dir / 'Resume.pdf'
        
        if not resume_path.exists():
            logger.error(f"Resume not found at {resume_path}")
            return None
        
        # Extract text from PDF
        with pdfplumber.open(resume_path) as pdf:
            text = '\n'.join(page.extract_text() for page in pdf.pages)
        
        # Extract profile information using Gemini
        profile = extract_profile_with_gemini(text)
        if not profile:
            logger.error("Failed to extract profile information")
            return None
            
        # Add last updated timestamp
        profile['last_updated'] = datetime.now().isoformat()
        
        # Store in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(profile, temp_file, indent=2)

        # Upload to GCS
        gcs_path = 'profile/profile.json'
        gcs.upload_file(temp_path, gcs_path)

        # Clean up temp file
        temp_path.unlink()
            
        logger.info(f"Successfully stored profile JSON in GCS at {gcs_path}")
        return profile
        
    except Exception as e:
        logger.error(f"Error creating profile JSON: {str(e)}")
        return None

if __name__ == "__main__":
    create_profile_json()