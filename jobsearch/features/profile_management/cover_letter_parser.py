import pdfplumber
from pathlib import Path
import os
import json
import tempfile
import re
from jobsearch.core.logging import setup_logging
from jobsearch.core.database import CoverLetterSection, get_session
from jobsearch.core.storage import gcs
from jobsearch.core.ai import StructuredPrompt

logger = setup_logging('cover_letter_parser')

# Initialize StructuredPrompt
structured_prompt = StructuredPrompt()

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
        # Define expected structure
        expected_structure = {
            "structure": {
                "greeting": str,
                "opening_approach": str,
                "body_sections": [{
                    "theme": str,
                    "content": str,
                    "writing_style": str
                }],
                "closing_style": str
            },
            "analysis": {
                "tone": str,
                "formality_level": int,
                "personalization_level": int,
                "strengths": [str],
                "areas_for_improvement": [str]
            }
        }

        # Example data structure
        example_data = {
            "structure": {
                "greeting": "Dear Hiring Manager,",
                "opening_approach": "Enthusiastic introduction referencing company mission",
                "body_sections": [{
                    "theme": "Technical Leadership",
                    "content": "Cloud infrastructure and team leadership experience",
                    "writing_style": "Professional and confident"
                }],
                "closing_style": "Strong call to action with enthusiasm"
            },
            "analysis": {
                "tone": "formal",
                "formality_level": 4,
                "personalization_level": 3,
                "strengths": ["Clear value proposition", "Strong relevant examples"],
                "areas_for_improvement": ["Could be more concise"]
            }
        }

        # Get structured response
        analysis = structured_prompt.get_structured_response(
            prompt=f"""Parse this cover letter text into sections and analyze the writing style.

Parse this cover letter:
{text}""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if not analysis:
            logger.error("Failed to parse cover letter")
            return None

        # Store analysis in GCS
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(analysis, temp_file, indent=2)

        # Upload to GCS
        gcs_path = 'analysis/cover_letter_style.json'
        gcs.upload_file(temp_path, gcs_path)

        # Clean up temp file
        temp_path.unlink()

        return analysis

    except Exception as e:
        logger.error(f"Error parsing cover letter text: {str(e)}")
        return None

def save_cover_letter_data(data):
    """Save parsed cover letter data to database using SQLAlchemy"""
    if not data:
        logger.warning("No cover letter data to save")
        return
        
    try:
        with get_session() as session:
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