"""Extract and parse profile information from documents."""
from pathlib import Path
import json
import re
import os
import tempfile
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

from jobsearch.core.ai import StructuredPrompt
from jobsearch.core.logging import setup_logging
from jobsearch.core.database import Experience, Skill, get_session
from jobsearch.core.storage import GCSManager
from jobsearch.core.pdf import PDFGenerator

logger = setup_logging('profile_parser')
storage = GCSManager()
pdf_generator = PDFGenerator()

# Configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from PDF file.
    
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
                title="Profile Document"
            ):
                return ""
                
            # Read the extracted text
            with open(temp_file.name, 'r') as f:
                text = f.read()
            return text
            
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return ""

def parse_profile_text(text):
    """Use Gemini to parse LinkedIn profile text into structured data"""
    try:
        from jobsearch.core.schemas import ProfileData, LinkedInExperience
        
        # Initialize StructuredPrompt
        structured_prompt = StructuredPrompt()

        # Create example data using Pydantic models
        example_data = ProfileData(
            experiences=[LinkedInExperience(
                company="Example Corp",
                title="Senior Engineer",
                start_date="2020-01",
                end_date="Present",
                description="Led development of cloud infrastructure",
                skills=["AWS", "Terraform", "Python"]
            )],
            additional_skills=["Docker", "Kubernetes", "CI/CD"]
        ).model_dump()

        # Get structured response
        profile_data = structured_prompt.get_structured_response(
            prompt=f"""Extract work experience and skills from this profile text.
Format dates as YYYY-MM.
Use 'Present' for current positions.
Include both explicitly mentioned skills and those implied by the experience.

Profile text:
{text}""",
            expected_structure=ProfileData,
            example_data=example_data
        )

        if profile_data:
            logger.info("Successfully parsed profile text")
            return profile_data
        else:
            logger.error("Failed to parse profile text")
            return None

    except Exception as e:
        logger.error(f"Error parsing profile text: {str(e)}")
        return None

def save_to_database(parsed_data):
    """Save parsed profile data to database using SQLAlchemy"""
    if not parsed_data:
        return False

    try:
        with get_session() as session:
            # Process each experience
            for exp_data in parsed_data["experiences"]:
                # Create or update experience
                experience = Experience(
                    company=exp_data["company"],
                    title=exp_data["title"],
                    start_date=exp_data["start_date"],
                    end_date=exp_data["end_date"],
                    description=exp_data["description"]
                )
                session.add(experience)
                session.flush()  # Get ID for relationships

                # Create or get skills and link to experience
                for skill_name in exp_data["skills"]:
                    skill = session.query(Skill).filter_by(skill_name=skill_name).first()
                    if not skill:
                        skill = Skill(skill_name=skill_name)
                        session.add(skill)
                    experience.skills.append(skill)

            # Add additional skills
            for skill_name in parsed_data.get("additional_skills", []):
                if not session.query(Skill).filter_by(skill_name=skill_name).first():
                    skill = Skill(skill_name=skill_name)
                    session.add(skill)

            logger.info("Successfully saved profile data to database")
            return True

    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")
        return False

def main():
    """Main entry point for profile parsing"""
    try:
        # Get profile PDF path
        pdf_path = Path(__file__).parent.parent / "inputs" / "Profile.pdf"
        if not pdf_path.exists():
            logger.error("Profile PDF not found")
            return False

        # Extract and parse text
        text = extract_text_from_pdf(pdf_path)
        if not text:
            return False

        parsed_data = parse_profile_text(text)
        if not parsed_data:
            return False

        # Save to database
        return save_to_database(parsed_data)

    except Exception as e:
        logger.error(f"Error in profile parsing: {str(e)}")
        return False

if __name__ == "__main__":
    main()