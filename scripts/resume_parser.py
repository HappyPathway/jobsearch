import pdfplumber
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
from utils import setup_logging
from models import Session, ResumeSection, ResumeExperience, ResumeEducation

logger = setup_logging('resume_parser')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text() + '\n'
    return text

def clean_json_with_gemini(json_str):
    """Use Gemini to clean and validate JSON data"""
    prompt = f"""You are a JSON validation system. Fix and return valid JSON only.
Input: {json_str}

Rules:
1. Return ONLY the fixed JSON - no other text, no code markers
2. Preserve all data but ensure valid JSON format
3. Remove any non-JSON artifacts
4. Ensure proper quote usage and escaping"""

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
            }
        )
        return json.loads(response.text.strip())
    except Exception as e:
        logger.error(f"Error cleaning JSON with Gemini: {str(e)}")
        return None

def parse_resume_text(text):
    """Use Gemini to parse resume text into structured data"""
    prompt = f"""You are a resume parsing system. Parse this text into JSON. 
ONLY return the JSON object itself, no other text, no 'json' prefix, no code block markers.

Text to parse:
{text}

Return this exact structure:
{{
    "summary": "brief career summary",
    "experience": [
        {{
            "company": "name",
            "title": "job title",
            "start_date": "YYYY-MM",
            "end_date": "YYYY-MM or Present",
            "location": "city/remote",
            "description": "key responsibilities and achievements"
        }}
    ],
    "education": [
        {{
            "institution": "school name",
            "degree": "degree type (e.g., BS, MS, PhD)",
            "field": "field of study",
            "graduation_date": "YYYY-MM",
            "gpa": "optional GPA"
        }}
    ],
    "certifications": [
        {{
            "name": "certification name",
            "issuer": "issuing organization",
            "date": "YYYY-MM",
            "expiration": "YYYY-MM or Never"
        }}
    ]
}}

Rules:
1. Format dates as YYYY-MM (use -01 if month unknown)
2. Use 'Present' for current positions and 'Never' for non-expiring certifications
3. Keep descriptions clear and concise
4. Do not use line breaks in descriptions
5. Include all education entries found (degrees, bootcamps, relevant courses)
6. For certifications, include both active and expired ones"""

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1000,
                "temperature": 0.1,
            }
        )
        
        # Clean up the response using Gemini
        json_str = response.text.strip()
        parsed = clean_json_with_gemini(json_str)
        
        if parsed:
            # Normalize experience entries
            for exp in parsed.get('experience', []):
                if not isinstance(exp, dict):
                    continue
                exp['company'] = exp.get('company', '').strip()
                exp['title'] = exp.get('title', '').strip()
                exp['start_date'] = exp.get('start_date', '').strip()
                exp['end_date'] = exp.get('end_date', 'Present').strip()
                exp['location'] = exp.get('location', '').strip()
                exp['description'] = ' '.join(exp.get('description', '').split())
            return parsed
        return None
            
    except Exception as e:
        logger.error(f"Error parsing resume with Gemini: {str(e)}")
        return None

def save_resume_data(data):
    """Save parsed resume data to database using SQLAlchemy"""
    if not data:
        return
        
    session = Session()
    
    try:
        # Clear existing data
        session.query(ResumeExperience).delete()
        session.query(ResumeEducation).delete()
        session.query(ResumeSection).filter(ResumeSection.section_name.in_(['summary', 'certifications'])).delete()
        
        # Save summary
        if data.get('summary'):
            summary_section = ResumeSection(
                section_name='summary',
                content=data['summary']
            )
            session.add(summary_section)
        
        # Save experiences
        for exp_data in data.get('experience', []):
            exp = ResumeExperience(
                company=exp_data.get('company', ''),
                title=exp_data.get('title', ''),
                start_date=exp_data.get('start_date', ''),
                end_date=exp_data.get('end_date', 'Present'),
                location=exp_data.get('location', ''),
                description=exp_data.get('description', '')
            )
            session.add(exp)
        
        # Save education
        for edu_data in data.get('education', []):
            edu = ResumeEducation(
                institution=edu_data.get('institution', ''),
                degree=edu_data.get('degree', ''),
                field=edu_data.get('field', ''),
                graduation_date=edu_data.get('graduation_date', ''),
                gpa=edu_data.get('gpa', '')
            )
            session.add(edu)
        
        # Save certifications
        if data.get('certifications'):
            cert_section = ResumeSection(
                section_name='certifications',
                content='\n'.join(data['certifications'])
            )
            session.add(cert_section)
        
        session.commit()
        logger.info("Successfully saved resume data to database")
        
    except Exception as e:
        logger.error(f"Error saving resume data: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

def main():
    pdf_path = Path(__file__).parent.parent / 'docs' / 'Resume.pdf'
    if not pdf_path.exists():
        logger.error(f"Error: Resume PDF not found at {pdf_path}")
        return
    
    try:
        # Extract text from PDF
        resume_text = extract_text_from_pdf(pdf_path)
        
        # Parse into structured data
        parsed_data = parse_resume_text(resume_text)
        
        # Save the parsed data
        save_resume_data(parsed_data)
        
        logger.info(f"Successfully processed resume from {pdf_path}")
        if parsed_data:
            logger.info(f"Found:")
            logger.info(f"- {len(parsed_data.get('experience', []))} experiences")
            logger.info(f"- {len(parsed_data.get('education', []))} education entries")
            logger.info(f"- {len(parsed_data.get('certifications', []))} certifications")
    except Exception as e:
        logger.error(f"Error processing resume: {str(e)}")

if __name__ == "__main__":
    main()