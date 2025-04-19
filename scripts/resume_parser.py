import pdfplumber
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re
from logging_utils import setup_logging
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
    if not json_str or not json_str.strip():
        logger.error("Empty JSON string provided to clean_json_with_gemini")
        return None

    prompt = f"""You are a JSON validation system. Fix and return valid JSON only.
Input: {json_str}

Rules:
1. Return ONLY the fixed JSON - no other text, no code markers
2. Preserve all data but ensure valid JSON format
3. Remove any non-JSON artifacts
4. Ensure proper quote usage and escaping
5. If the input is invalid, return a basic valid JSON structure"""

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 1000,
            }
        )
        
        # Check for empty response
        if not response or not response.text or not response.text.strip():
            logger.error("Empty response received from Gemini")
            return None
            
        # Clean up the response
        json_str = response.text.strip()
        
        # Remove markdown formatting if present
        json_str = re.sub(r'^```.*?\n', '', json_str)  # Remove opening ```json
        json_str = re.sub(r'\n```$', '', json_str)     # Remove closing ```
        
        # Try to extract just the JSON object if there's other text
        match = re.search(r'({[\s\S]*})', json_str)
        if match:
            json_str = match.group(1)
            
        # Fix common JSON issues
        json_str = re.sub(r':\s*null\b', ': ""', json_str)  # Replace null with empty string
        json_str = re.sub(r':\s*undefined\b', ': ""', json_str)  # Replace undefined with empty string
        json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
        json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas in arrays
        
        # Advanced cleaning for other common JSON syntax errors
        json_str = re.sub(r'([{,])\s*"([^"]+)"\s*:\s*([^"{}\[\],]+)([},])', r'\1"\2":"\3"\4', json_str)  # Add quotes around unquoted string values
        json_str = re.sub(r'\n', ' ', json_str)  # Remove newlines in JSON string
        json_str = re.sub(r'"\s*\n\s*"', '" "', json_str)  # Join multiline strings
        json_str = re.sub(r'"{2,}', '"', json_str)  # Fix doubled quotes
        
        # Additional safety check for badly formed JSON with extra trailing text
        if not json_str.endswith("}"):
            end_brace_pos = json_str.rfind("}")
            if end_brace_pos > 0:
                json_str = json_str[:end_brace_pos+1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing error after cleaning: {str(je)}")
            logger.debug(f"Cleaned but invalid JSON: {json_str}")
            
            # Try one more approach - use a second call to Gemini specifically for fixing the JSON
            retry_prompt = f"""Fix this invalid JSON. ONLY return the fixed JSON with no explanation or other text:

{json_str}"""
            
            try:
                retry_response = model.generate_content(
                    retry_prompt,
                    generation_config={
                        "temperature": 0.1,
                        "max_output_tokens": 1000,
                    }
                )
                
                retry_json = retry_response.text.strip()
                # Remove markdown formatting
                retry_json = re.sub(r'^```.*?\n', '', retry_json)
                retry_json = re.sub(r'\n```$', '', retry_json)
                
                # Attempt to parse the fixed JSON
                return json.loads(retry_json)
            except Exception:
                logger.error("Failed to fix JSON even with second Gemini attempt")
                return None
            
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