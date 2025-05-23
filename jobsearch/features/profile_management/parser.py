"""Extract and parse profile information from documents."""

import pdfplumber
import json
import re
from pathlib import Path
import os
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

from jobsearch.core.ai import StructuredPrompt
from jobsearch.core.logging import setup_logging
from jobsearch.core.database import Experience, Skill, get_session
from jobsearch.core.storage import gcs

logger = setup_logging('profile_parser')

# Configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return None

def parse_profile_text(text):
    """Use Gemini to parse LinkedIn profile text into structured data"""
    try:
        from jobsearch.core.schemas import ProfileData, LinkedInExperience
        
        # Initialize StructuredPrompt
        structured_prompt = StructuredPrompt()

        # Create example data using Pydantic models
        example_data = ProfileData(
            experiences=[LinkedInExperience(
                company="Tech Corp",
                title="Senior Software Engineer",
                start_date="2020-01",
                end_date="Present",
                description="Led development of cloud infrastructure",
                skills=["Python", "AWS", "Terraform"]
            )],
            additional_skills=["Docker", "Kubernetes"]
        ).model_dump()

        response = structured_prompt.get_structured_response(
            prompt=f"""Extract structured profile data from this text:

{text}

Format the data to show:
1. List of work experiences with company, title, dates, and skills used
2. Additional skills mentioned but not tied to specific roles""",
            expected_structure=ProfileData,
            example_data=example_data
        )

        if response:
            logger.info("Successfully parsed profile text")
            return response

        logger.error("Failed to parse profile text")
        return None

    except Exception as e:
        logger.error(f"Error parsing profile text: {str(e)}")
        return None

def save_profile_data(parsed_data):
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

            session.commit()
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
        return save_profile_data(parsed_data)

    except Exception as e:
        logger.error(f"Error in profile parsing: {str(e)}")
        return False

if __name__ == "__main__":
    main()