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
import gcs

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
        prompt = """Parse the LinkedIn profile text into structured data.
Focus on extracting:
1. Experiences with accomplishments
2. Skills with context
3. Educational background
4. Certifications and awards

Return a JSON object with all extracted information."""

        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.1,
            }
        )

        # Parse response into structured data
        data = json.loads(response.text)
        
        # Store raw data in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(data, temp_file, indent=2)

        # Upload to GCS
        gcs_path = 'profile/linkedin_raw.json'
        gcs.upload_file(temp_path, gcs_path)

        # Clean up temp file
        temp_path.unlink()
        
        logger.info(f"Stored raw LinkedIn data in GCS at {gcs_path}")
        return data

    except Exception as e:
        logger.error(f"Error parsing profile text: {str(e)}")
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