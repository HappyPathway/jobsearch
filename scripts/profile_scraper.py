import pdfplumber
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re
from utils import setup_logging
from models import Session, Experience, Skill, engine

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
    logger.info("Starting profile text parsing with Gemini")
    prompt = f"""Parse this text into a single line of JSON with no line breaks.
Output only the JSON object, nothing else.

Text to parse:
{text}

Example format (single line, replace with actual data):
{{"experiences":[{{"company":"Company","title":"Title","start_date":"2020-01","end_date":"Present","description":"Work description"}}],"skills":["Skill1"],"certifications":[],"education":[{{"school":"School","degree":"Degree","field":"Field","start_date":"2020-01","end_date":"2020-12"}}]}}

Rules:
1. Output must be a single line of valid JSON
2. Use double quotes for all strings
3. No trailing commas
4. No line breaks or formatting
5. Format dates as YYYY-MM
6. Use 'Present' for current positions
7. Keep descriptions concise
8. Extract key skills
9. Only include stated certifications
10. Only include information from the text"""

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        logger.debug("Sending text to Gemini for parsing")
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.1,
            }
        )
        
        # Clean up the response
        json_str = response.text.strip()
        logger.debug("Received response from Gemini")
        
        # Extract just the JSON object
        match = re.search(r'({.*})', json_str)
        if match:
            json_str = match.group(1)
        
        # Basic cleanup
        json_str = json_str.replace('\n', ' ').replace('\r', ' ')
        json_str = re.sub(r'\s+', ' ', json_str)
        
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {str(e)}")
            return None
        
        # Normalize and validate data
        logger.info("Normalizing parsed data")
        normalized = {
            "experiences": [],
            "skills": [],
            "certifications": [],
            "education": []
        }
        
        # Normalize experiences
        for exp in parsed.get('experiences', []):
            if isinstance(exp, dict):
                normalized["experiences"].append({
                    "company": str(exp.get('company', '')).strip(),
                    "title": str(exp.get('title', '')).strip(),
                    "start_date": str(exp.get('start_date', '')).strip(),
                    "end_date": str(exp.get('end_date', 'Present')).strip(),
                    "description": ' '.join(str(exp.get('description', '')).split())
                })
        
        # Normalize lists
        normalized["skills"] = [str(s).strip() for s in parsed.get('skills', []) if s]
        normalized["certifications"] = [str(c).strip() for c in parsed.get('certifications', []) if c]
        
        # Normalize education
        for edu in parsed.get('education', []):
            if isinstance(edu, dict):
                normalized["education"].append({
                    "school": str(edu.get('school', '')).strip(),
                    "degree": str(edu.get('degree', '')).strip(),
                    "field": str(edu.get('field', '')).strip() if edu.get('field') else '',
                    "start_date": str(edu.get('start_date', '')).strip(),
                    "end_date": str(edu.get('end_date', '')).strip()
                })
        
        logger.info(f"Successfully parsed profile data: {len(normalized['experiences'])} experiences, {len(normalized['skills'])} skills")
        return normalized
    except Exception as e:
        logger.error(f"Error parsing profile with Gemini: {str(e)}")
        return None

def save_to_database(parsed_data):
    """Save parsed profile data to database using SQLAlchemy"""
    if not parsed_data:
        logger.warning("No parsed data to save to database")
        return
        
    logger.info("Saving parsed data to database")
    session = Session()
    
    try:
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
        
        session.commit()
        logger.info(f"Saved {skill_count} skills and {exp_count} experiences to database")
        
    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()

def main():
    pdf_path = Path(__file__).parent.parent / 'docs' / 'Profile.pdf'
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