import pdfplumber
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re
import tempfile
from logging_utils import setup_logging
from models import Session, ResumeSection, ResumeExperience, ResumeEducation
from gcs_utils import gcs

logger = setup_logging('resume_parser')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        # Extract text using pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = '\n'.join(page.extract_text() for page in pdf.pages)
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return None

def clean_json_with_gemini(json_str):
    """Use Gemini to clean and validate JSON data"""
    try:
        prompt = f"""Clean and validate this JSON data from a resume parser. Ensure all fields are properly formatted and filled.
If any required fields are missing or invalid, provide reasonable defaults based on context.

JSON to clean:
{json_str}

Return only the cleaned JSON object, no other text."""

        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.1,
            }
        )
        
        cleaned_json = response.text.strip()
        # Remove markdown formatting if present
        cleaned_json = re.sub(r'^```.*?\n', '', cleaned_json)
        cleaned_json = re.sub(r'\n```$', '', cleaned_json)
        
        return json.loads(cleaned_json)
        
    except Exception as e:
        logger.error(f"Error cleaning JSON with Gemini: {str(e)}")
        return None

def parse_resume_text(text):
    """Use Gemini to parse resume text into structured data"""
    try:
        prompt = f"""Parse this resume text into detailed structured data.
Focus on:
1. Contact information
2. Professional summary
3. Experience entries with accomplishments
4. Skills and expertise
5. Education and certifications

Format the response as a clean JSON object."""

        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.1,
            }
        )
        
        # Clean and validate JSON
        parsed_data = clean_json_with_gemini(response.text)
        if not parsed_data:
            return None
            
        return parsed_data
        
    except Exception as e:
        logger.error(f"Error parsing resume text: {str(e)}")
        return None

def save_resume_data(data):
    """Save parsed resume data to database using SQLAlchemy"""
    if not data:
        logger.warning("No resume data to save")
        return
        
    try:
        with Session() as session:
            # Store sections
            for section_name, content in data.get('sections', {}).items():
                section = ResumeSection(
                    section_name=section_name,
                    content=content
                )
                session.add(section)
            
            # Store experiences
            for exp in data.get('experiences', []):
                experience = ResumeExperience(
                    company=exp.get('company', ''),
                    title=exp.get('title', ''),
                    dates=exp.get('dates', ''),
                    location=exp.get('location', ''),
                    description=json.dumps(exp.get('description', []))
                )
                session.add(experience)
            
            # Store education
            for edu in data.get('education', []):
                education = ResumeEducation(
                    institution=edu.get('institution', ''),
                    degree=edu.get('degree', ''),
                    field=edu.get('field', ''),
                    graduation_date=edu.get('graduation_date', ''),
                    gpa=edu.get('gpa', '')
                )
                session.add(education)
                
        logger.info("Successfully saved resume data to database")
        
    except Exception as e:
        logger.error(f"Error saving resume data: {str(e)}")
        raise

def main():
    """Main entry point for resume parsing"""
    try:
        # Get resume from docs directory
        docs_dir = Path(__file__).parent.parent / 'inputs'
        resume_path = docs_dir / 'Resume.pdf'
        
        if not resume_path.exists():
            logger.error(f"Resume not found at {resume_path}")
            return
        
        # Extract text from PDF
        resume_text = extract_text_from_pdf(resume_path)
        if not resume_text:
            logger.error("Failed to extract text from resume")
            return
        
        # Parse resume text into structured data 
        parsed_data = parse_resume_text(resume_text)
        if not parsed_data:
            logger.error("Failed to parse resume text")
            return
            
        # Store raw data in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(parsed_data, temp_file, indent=2)

        # Upload to GCS
        gcs_path = 'analysis/resume_raw.json'
        gcs.upload_file(temp_path, gcs_path)
        
        # Clean up temp file
        temp_path.unlink()
        
        # Save structured data to database
        save_resume_data(parsed_data)
        logger.info("Successfully completed resume parsing process")
        
    except Exception as e:
        logger.error(f"Error in resume parsing process: {str(e)}")

if __name__ == "__main__":
    main()