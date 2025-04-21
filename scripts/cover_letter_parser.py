import pdfplumber
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import tempfile
from logging_utils import setup_logging
from models import CoverLetterSection, session_scope
from gcs_utils import gcs

logger = setup_logging('cover_letter_parser')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_text_from_pdf(file_path):
    """Extract text from PDF file in docs directory"""
    try:
        # Extract text from PDF
        with pdfplumber.open(file_path) as pdf:
            text = '\n'.join(page.extract_text() for page in pdf.pages)
        return text
            
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {str(e)}")
        return None

def parse_cover_letter_text(text):
    """Use Gemini to parse cover letter text into structured data"""
    try:
        prompt = """Parse this cover letter text into sections and analyze the writing style.
Extract:
1. Greeting style
2. Opening paragraph approach
3. Body content themes
4. Closing style
5. Overall tone and formality level

Return a JSON object with the analysis."""

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
        
        # Store analysis in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(data, temp_file, indent=2)

        # Upload to GCS
        gcs_path = 'analysis/cover_letter_style.json'
        gcs.upload_file(temp_path, gcs_path)

        # Clean up temp file
        temp_path.unlink()
        
        logger.info(f"Stored cover letter style analysis in GCS at {gcs_path}")
        return data
        
    except Exception as e:
        logger.error(f"Error parsing cover letter text: {str(e)}")
        return None

def save_cover_letter_data(data):
    """Save parsed cover letter data to database using SQLAlchemy"""
    if not data:
        logger.warning("No cover letter data to save")
        return
        
    try:
        with session_scope() as session:
            # Store each section in the database
            for section_name, content in data.items():
                section = CoverLetterSection(
                    section_name=section_name,
                    content=json.dumps(content) if isinstance(content, dict) else str(content)
                )
                session.merge(section)
                
        logger.info("Successfully saved cover letter data to database")
        
    except Exception as e:
        logger.error(f"Error saving cover letter data: {str(e)}")
        raise

def main():
    """Main entry point for cover letter parsing"""
    try:
        # Get cover letter from docs directory
        docs_dir = Path(__file__).parent.parent / 'inputs'
        cover_letter_path = docs_dir / 'CoverLetter.pdf'
        
        if not cover_letter_path.exists():
            logger.error(f"Cover letter not found at {cover_letter_path}")
            return
        
        # Extract text from PDF
        cover_letter_text = extract_text_from_pdf(cover_letter_path)
        if not cover_letter_text:
            logger.error("Failed to extract text from cover letter")
            return
        
        # Parse and analyze cover letter text
        parsed_data = parse_cover_letter_text(cover_letter_text)
        if not parsed_data:
            logger.error("Failed to parse cover letter text")
            return
            
        # Store raw data and analysis in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(parsed_data, temp_file, indent=2)

        # Upload to GCS
        gcs_path = 'analysis/cover_letter_style.json'
        gcs.upload_file(temp_path, gcs_path)
        
        # Clean up temp file
        temp_path.unlink()
        
        # Save analysis to database
        save_cover_letter_data(parsed_data)
        logger.info("Successfully completed cover letter parsing process")
        
    except Exception as e:
        logger.error(f"Error in cover letter parsing process: {str(e)}")

if __name__ == "__main__":
    main()