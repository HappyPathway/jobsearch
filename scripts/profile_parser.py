import pdfplumber
import json
import re
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
from utils import setup_logging

logger = setup_logging('profile_parser')

# Configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_profile_with_gemini(text):
    """Use Gemini to extract structured profile information from resume text"""
    try:
        prompt = f"""You are an expert at parsing resumes for technical roles. Extract only the most significant skills and expertise from this resume, focusing on technologies and practices that appear multiple times or in meaningful contexts.

Rules for skill analysis:
1. Only include skills with significant usage (mentioned multiple times or in important contexts)
2. Weight recent experience more heavily
3. Consider the context - implementation/architecture vs just using a tool
4. Look for patterns of expertise (e.g. multiple AWS services = strong AWS knowledge)

Resume text to analyze:
{text}

Provide a JSON response with this exact structure (no comments or extra text):
{{
    "contact_info": {{
        "name": str,
        "email": str,
        "phone": str,
        "location": str,
        "linkedin": str
    }},
    "core_skills": {{
        "infrastructure_and_cloud": [
            {{
                "name": str,
                "proficiency": "expert|advanced|intermediate",
                "years": int,
                "last_used": "YYYY",
                "mentions": int,
                "context": str
            }}
        ],
        "development_and_automation": [],
        "platforms_and_tools": [],
        "methodologies": []
    }},
    "experience": [
        {{
            "company": str,
            "title": str,
            "dates": str,
            "location": str,
            "description": [str]
        }}
    ],
    "education": []
}}

Notes:
- Proficiency levels:
  expert = Deep expertise, multiple years, leadership/architecture level
  advanced = Solid working knowledge, regular usage
  intermediate = Basic working knowledge, occasional usage
- Only include skills mentioned multiple times or in significant contexts
- Group related technologies (e.g. group AWS services under AWS expertise)
- Include brief context about how the skill was used"""

        model = genai.GenerativeModel('gemini-1.5-pro')
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
                if 'last_used' not in skill:
                    skill['last_used'] = '2024'
                if 'mentions' not in skill:
                    skill['mentions'] = 1
                if 'context' not in skill:
                    skill['context'] = ''
        
        # If location is empty but we have experience entries, infer from most recent
        if not profile['contact_info']['location'] and profile['experience']:
            recent_locations = [exp.get('location', '') for exp in profile['experience'][:3]]
            if any(loc for loc in recent_locations if 'San Francisco' in loc or 'San Jose' in loc or 'Bay' in loc):
                profile['contact_info']['location'] = 'Bay Area, CA'
            elif any(recent_locations):
                profile['contact_info']['location'] = recent_locations[0]
        
        return profile
        
    except Exception as e:
        logger.error(f"Error extracting profile with Gemini: {str(e)}")
        logger.error(f"Full error: {str(e.__class__.__name__)}: {str(e)}")
        return None

def create_profile_json():
    """Create JSON profile from resume"""
    docs_dir = Path(__file__).parent.parent / 'docs'
    resume_path = docs_dir / 'Resume.pdf'
    
    if not resume_path.exists():
        logger.error(f"Resume not found at {resume_path}")
        return None
    
    try:
        # Extract text from PDF
        with pdfplumber.open(resume_path) as pdf:
            text = '\n'.join(page.extract_text() for page in pdf.pages)
        
        # Extract profile information using Gemini
        profile = extract_profile_with_gemini(text)
        if not profile:
            logger.error("Failed to extract profile information")
            return None
            
        # Add last updated timestamp
        profile['last_updated'] = resume_path.stat().st_mtime
        
        # Save to profile.json
        profile_path = docs_dir / 'profile.json'
        with open(profile_path, 'w') as f:
            json.dump(profile, f, indent=2)
            
        logger.info(f"Successfully created profile JSON at {profile_path}")
        return profile
        
    except Exception as e:
        logger.error(f"Error creating profile JSON: {str(e)}")
        return None

if __name__ == "__main__":
    create_profile_json()