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
from structured_prompt import StructuredPrompt

logger = setup_logging('resume_parser')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize StructuredPrompt
structured_prompt = StructuredPrompt()

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

def parse_resume_text(text):
    """Use Gemini to parse resume text into structured data"""
    try:
        # Define expected structure
        expected_structure = {
            "contact_info": {
                "name": str,
                "email": str,
                "phone": str,
                "location": str,
                "linkedin": str
            },
            "summary": str,
            "experience": [{
                "company": str,
                "title": str,
                "start_date": str,
                "end_date": str,
                "description": str,
                "achievements": [str]
            }],
            "education": [{
                "institution": str,
                "degree": str,
                "field": str,
                "graduation_date": str
            }],
            "skills": {
                "technical": [str],
                "soft": [str]
            },
            "certifications": [{
                "name": str,
                "issuer": str,
                "date": str
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
            "summary": "Senior software engineer with 10 years of experience...",
            "experience": [{
                "company": "Tech Corp",
                "title": "Senior Software Engineer",
                "start_date": "2020-01",
                "end_date": "Present",
                "description": "Led development of cloud infrastructure",
                "achievements": [
                    "Reduced deployment time by 75%",
                    "Implemented CI/CD pipeline"
                ]
            }],
            "education": [{
                "institution": "University of Example",
                "degree": "Bachelor of Science",
                "field": "Computer Science",
                "graduation_date": "2010-05"
            }],
            "skills": {
                "technical": ["Python", "AWS", "Kubernetes"],
                "soft": ["Leadership", "Communication"]
            },
            "certifications": [{
                "name": "AWS Solutions Architect",
                "issuer": "Amazon Web Services",
                "date": "2021-06"
            }]
        }

        # Get structured response
        parsed_data = structured_prompt.get_structured_response(
            prompt=f"""Parse this resume text into detailed structured data.
Focus on:
1. Contact information
2. Professional summary
3. Experience entries with accomplishments
4. Skills and expertise
5. Education and certifications

Resume text to parse:
{text}""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if not parsed_data:
            logger.error("Failed to parse resume text")
            return None

        # Store parsed data in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(parsed_data, temp_file, indent=2)

        # Upload to GCS
        gcs_path = 'parsed/resume_parsed.json'
        gcs.upload_file(temp_path, gcs_path)

        # Clean up temp file
        temp_path.unlink()

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
            
        # Save structured data to database
        save_resume_data(parsed_data)
        logger.info("Successfully completed resume parsing process")
        
    except Exception as e:
        logger.error(f"Error in resume parsing process: {str(e)}")

if __name__ == "__main__":
    main()