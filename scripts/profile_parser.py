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

logger = setup_logging('profile_parser')

# Configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_profile_with_gemini(text):
    """Use Gemini to extract structured profile information from resume text"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = """Extract structured profile information from this resume text.
Include:
1. Contact information (name, email, phone, location, LinkedIn)
2. Core skills organized by category
3. Experience entries with achievements
4. Education history

Return as a clean JSON object with consistent formatting."""

        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2500,
                "temperature": 0.1,
            }
        )
        
        # Clean up response and extract JSON
        json_str = response.text.strip()
        
        # Remove markdown formatting
        json_str = re.sub(r'^```.*?\n', '', json_str)  # Remove opening ```json
        json_str = re.sub(r'\n```$', '', json_str)     # Remove closing ```
        json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)  # Remove comments
        
        # Fix common JSON issues
        json_str = re.sub(r':\s*null\b', ': ""', json_str)  # Replace null with empty string
        json_str = re.sub(r':\s*undefined\b', ': ""', json_str)  # Replace undefined with empty string
        
        # Fix URL formatting
        json_str = re.sub(r'"linkedin":\s*"?(http[^"}\s]+)"?', r'"linkedin": "\1"', json_str)
        
        # Try to extract just the JSON object if there's other text
        match = re.search(r'({[\s\S]*})', json_str)
        if match:
            json_str = match.group(1)
        
        try:
            # Parse and validate JSON structure
            profile = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from Gemini: {str(e)}")
            logger.error(f"JSON content: {json_str}")
            return None
        
        # Ensure all required fields exist
        required_fields = {
            'contact_info': {
                'name': '', 'email': '', 'phone': '', 
                'location': '', 'linkedin': ''
            },
            'core_skills': {
                'infrastructure_and_cloud': [],
                'development_and_automation': [],
                'platforms_and_tools': [],
                'methodologies': []
            },
            'experience': [],
            'education': []
        }
        
        # Validate and set defaults for missing fields
        for field, default in required_fields.items():
            if field not in profile:
                profile[field] = default
                
        # Validate contact info structure
        for field, default in required_fields['contact_info'].items():
            if field not in profile['contact_info']:
                profile['contact_info'][field] = default
        
        # Validate core_skills structure
        for category, default in required_fields['core_skills'].items():
            if category not in profile['core_skills']:
                profile['core_skills'][category] = default
            
            # Ensure each skill has all required fields
            for skill in profile['core_skills'][category]:
                if 'name' not in skill:
                    continue
                if 'proficiency' not in skill:
                    skill['proficiency'] = 'intermediate'
                if 'years' not in skill:
                    skill['years'] = 1
        
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