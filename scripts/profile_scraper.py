import pdfplumber
from pathlib import Path
import os
import json
import re
import tempfile
from dotenv import load_dotenv
from logging_utils import setup_logging
from models import Experience, Skill, get_session
from gcs_utils import gcs
from structured_prompt import StructuredPrompt

logger = setup_logging('profile_scraper')

load_dotenv()

# Initialize StructuredPrompt
structured_prompt = StructuredPrompt()

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
        # Define expected structure
        expected_structure = {
            "experiences": [{
                "company": str,
                "title": str,
                "start_date": str,
                "end_date": str,
                "description": str
            }],
            "skills": [str],
            "education": [{
                "institution": str,
                "degree": str,
                "field": str,
                "graduation_date": str
            }],
            "certifications": [{
                "name": str,
                "issuer": str,
                "date": str
            }]
        }

        # Example data structure
        example_data = {
            "experiences": [{
                "company": "Tech Corp",
                "title": "Senior Software Engineer",
                "start_date": "2020-01",
                "end_date": "Present",
                "description": "Led development of cloud infrastructure"
            }],
            "skills": ["Python", "Cloud Architecture", "DevOps"],
            "education": [{
                "institution": "Example University",
                "degree": "Bachelor of Science",
                "field": "Computer Science",
                "graduation_date": "2015-05"
            }],
            "certifications": [{
                "name": "AWS Solutions Architect",
                "issuer": "Amazon Web Services",
                "date": "2021-06"
            }]
        }

        # Get structured response
        profile_data = structured_prompt.get_structured_response(
            prompt=f"""Extract structured data from this LinkedIn profile text.
Focus on work experience, skills, education, and certifications.

Profile text to process:
{text}""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if not profile_data:
            logger.error("Failed to parse profile data")
            return None

        return profile_data

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