import pdfplumber
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
from utils import setup_logging
from models import CoverLetterSection, get_session

logger = setup_logging('cover_letter_parser')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text() + '\n'
    return text

def parse_cover_letter_text(text):
    """Use Gemini to parse cover letter text into structured data"""
    prompt = f"""You are a cover letter parsing system. Parse this text into JSON.
ONLY return the JSON object itself, no other text, no prefixes, no code block markers.

Text to parse:
{text}

Return this exact structure:
{{
    "greeting": "greeting text",
    "introduction": "first paragraph introducing the candidate",
    "body": [
        "paragraph 1 discussing skills and experience",
        "paragraph 2 discussing qualifications",
        "etc..."
    ],
    "closing": "closing paragraph",
    "signature": "signature text",
    "key_points": [
        "main point 1",
        "main point 2",
        "etc..."
    ]
}}

Rules:
1. Preserve the original content but split into logical sections
2. Extract 3-5 key points that make this candidate stand out
3. Do not add information that isn't in the original text
4. Keep paragraphs in their original order"""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1000,
                "temperature": 0.1,
            }
        )
        
        # Clean up the response
        json_str = response.text.strip()
        
        # Remove any non-JSON content
        while not json_str.startswith('{'):
            json_str = json_str[1:]
        while not json_str.endswith('}'):
            json_str = json_str[:-1]
            
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Error parsing cover letter with Gemini: {str(e)}")
        return None

def save_cover_letter_data(data):
    """Save parsed cover letter data to database using SQLAlchemy"""
    if not data:
        return

    try:
        with get_session() as session:
            # Clear existing data
            session.query(CoverLetterSection).delete()
            
            # Save each section
            sections_to_save = {
                'greeting': data.get('greeting'),
                'introduction': data.get('introduction'),
                'body': '\n\n'.join(data.get('body', [])),
                'closing': data.get('closing'),
                'signature': data.get('signature'),
                'key_points': '\n'.join(data.get('key_points', []))
            }
            
            for section_name, content in sections_to_save.items():
                if content:
                    section = CoverLetterSection(
                        section_name=section_name,
                        content=content
                    )
                    session.add(section)
            
            logger.info("Successfully saved cover letter data")
            
    except Exception as e:
        logger.error(f"Error saving cover letter data: {str(e)}")
        raise

def main():
    pdf_path = Path(__file__).parent.parent / 'docs' / 'CoverLetter.pdf'
    if not pdf_path.exists():
        logger.error(f"Error: Cover Letter PDF not found at {pdf_path}")
        return
    
    try:
        # Extract text from PDF
        cover_letter_text = extract_text_from_pdf(pdf_path)
        
        # Use Gemini to parse into structured data
        parsed_data = parse_cover_letter_text(cover_letter_text)
        
        # Save the parsed data
        save_cover_letter_data(parsed_data)
        
        logger.info(f"Successfully processed cover letter from {pdf_path}")
        if parsed_data:
            logger.info(f"Found:")
            logger.info(f"- {len(parsed_data.get('body', []))} body paragraphs")
            logger.info(f"- {len(parsed_data.get('key_points', []))} key points")
    except Exception as e:
        logger.error(f"Error processing cover letter: {str(e)}")

if __name__ == "__main__":
    main()