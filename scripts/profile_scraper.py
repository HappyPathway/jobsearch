import pdfplumber
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re
import tempfile
from logging_utils import setup_logging
from models import Experience, Skill, get_session
from gcs_utils import gcs

logger = setup_logging('profile_scraper')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    logger.info(f"Extracting text from PDF: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() + '\n'
            logger.info(f"Successfully extracted {len(text)} characters from PDF")
            return text
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {str(e)}")
        raise

def parse_profile_text(text):
    """Use Gemini to parse LinkedIn profile text into structured data"""
    try:
        prompt = f"""You are a JSON data extraction system. Extract structured data from this LinkedIn profile text and return it as a JSON object. The response must be a valid JSON object and nothing else - no markdown, no explanations, no other text.

Profile text to process:
{text}

Required JSON structure:
{{
    "experiences": [
        {{
            "company": "string",
            "title": "string",
            "start_date": "string",
            "end_date": "string",
            "description": "string"
        }}
    ],
    "skills": ["string"],
    "education": [
        {{
            "institution": "string",
            "degree": "string",
            "field": "string",
            "graduation_date": "string"
        }}
    ],
    "certifications": [
        {{
            "name": "string",
            "issuer": "string",
            "date": "string"
        }}
    ]
}}"""
        
        logger.info("Sending profile text to Gemini for parsing")
        
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.1,
            }
        )
        
        # Clean the response text to ensure it's valid JSON
        response_text = response.text.strip()
        # Remove any markdown code block indicators
        response_text = re.sub(r'^```json\s*|\s*```$', '', response_text)
        response_text = re.sub(r'^```\s*|\s*```$', '', response_text)
        
        # Validate and parse JSON
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received from Gemini: {response_text}")
            logger.error(f"JSON parse error: {str(e)}")
            raise ValueError("Gemini returned invalid JSON format")
        
        # Store raw data in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(data, temp_file, indent=2)

        # Upload to GCS using the global gcs instance
        gcs_path = 'profile/linkedin_raw.json'
        gcs.upload_file(temp_path, gcs_path)

        # Clean up temp file
        temp_path.unlink()
        
        logger.info(f"Stored raw LinkedIn data in GCS at {gcs_path}")
        return data

    except Exception as e:
        logger.error(f"Error parsing profile text: {str(e)}")
        if 'response' in locals():
            logger.error(response.text)
        return None

def save_to_database(parsed_data):
    """Save parsed profile data to database using SQLAlchemy"""
    if not parsed_data:
        logger.warning("No parsed data to save to database")
        return
        
    logger.info("Saving parsed data to database")
    
    try:
        with get_session() as session:
            # Clear existing data
            session.query(Experience).delete()
            session.query(Skill).delete()
            
            # Save skills first
            skill_count = 0
            skill_objects = {}
            for skill_name in parsed_data.get('skills', []):
                skill = Skill(skill_name=skill_name)
                session.add(skill)
                skill_objects[skill_name] = skill
                skill_count += 1
            
            # Save experiences and link skills
            exp_count = 0
            for exp_data in parsed_data.get('experiences', []):
                exp = Experience(
                    company=exp_data.get('company', ''),
                    title=exp_data.get('title', ''),
                    start_date=exp_data.get('start_date', ''),
                    end_date=exp_data.get('end_date', 'Present'),
                    description=exp_data.get('description', '')
                )
                
                # Link relevant skills
                exp_text = exp_data.get('description', '').lower()
                for skill_name, skill in skill_objects.items():
                    if skill_name.lower() in exp_text:
                        exp.skills.append(skill)
                
                session.add(exp)
                exp_count += 1
            
            logger.info(f"Saved {skill_count} skills and {exp_count} experiences to database")
            
    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")
        raise

def main():
    pdf_path = Path(__file__).parent.parent / 'inputs' / 'Profile.pdf'
    logger.info(f"Starting profile scraping process")
    
    if not pdf_path.exists():
        logger.error(f"Error: LinkedIn profile PDF not found at {pdf_path}")
        return
    
    try:
        # Extract text from PDF
        profile_text = extract_text_from_pdf(pdf_path)
        
        # Parse into structured data
        parsed_data = parse_profile_text(profile_text)
        
        # Save the parsed data
        save_to_database(parsed_data)
        
        logger.info(f"Successfully completed profile scraping process")
        if parsed_data:
            logger.info(f"Summary of processed data:")
            logger.info(f"- {len(parsed_data.get('experiences', []))} experiences")
            logger.info(f"- {len(parsed_data.get('skills', []))} skills")
    except Exception as e:
        logger.error(f"Error processing profile: {str(e)}")

if __name__ == "__main__":
    main()