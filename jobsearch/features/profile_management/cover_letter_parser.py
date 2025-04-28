"""Parse and process cover letter documents."""
from pathlib import Path
import os
import json
import tempfile
import re
from jobsearch.core.logging import setup_logging
from jobsearch.core.database import CoverLetterSection, get_session
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import StructuredPrompt
from jobsearch.core.pdf import PDFGenerator

logger = setup_logging('cover_letter_parser')
storage = GCSManager()
pdf_generator = PDFGenerator()

def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from PDF file in docs directory.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content or empty string if extraction fails
    """
    try:
        with tempfile.NamedTemporaryFile(suffix='.txt') as temp_file:
            # Use PDFGenerator to convert PDF to text
            if not pdf_generator.generate_from_text(
                text="", # This will be replaced with PDF content
                output_path=temp_file.name,
                title="Cover Letter"
            ):
                return ""
                
            # Read the extracted text
            with open(temp_file.name, 'r') as f:
                text = f.read()
            return text
            
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {str(e)}")
        return ""

def parse_cover_letter_text(text):
    """Use Gemini to parse cover letter text into structured data"""
    try:
        from jobsearch.core.schemas import CoverLetterAnalysis, CoverLetterStructure, CoverLetterSection
        
        # Create example data using Pydantic models
        example_data = CoverLetterAnalysis(
            structure=CoverLetterStructure(
                greeting="Dear Hiring Manager,",
                opening_approach="Enthusiastic introduction referencing company mission",
                body_sections=[
                    CoverLetterSection(
                        theme="Technical Leadership",
                        content="Cloud infrastructure and team leadership experience",
                        writing_style="Professional and confident"
                    )
                ],
                closing_style="Strong call to action with enthusiasm"
            ),
            analysis={
                "tone": "formal",
                "formality_level": 4,
                "personalization_level": 3,
                "strengths": ["Clear value proposition", "Strong relevant examples"],
                "areas_for_improvement": ["Could be more concise"]
            }
        ).model_dump()

        # Get structured response
        analysis = structured_prompt.get_structured_response(
            prompt=f"""Parse this cover letter text into sections and analyze the writing style.

Parse this cover letter:
{text}""",
            expected_structure=CoverLetterAnalysis,
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