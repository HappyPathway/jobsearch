"""Parse and extract information from resume documents."""
from pathlib import Path
from typing import Dict, List, Optional

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.models import ResumeSection, ResumeExperience, ResumeEducation
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import AIEngine
from jobsearch.core.pdf import PDFGenerator
from jobsearch.core.schemas import ResumeData, Education, Experience

# Initialize core components
logger = setup_logging('resume_parser')
storage = GCSManager()
pdf_generator = PDFGenerator()
ai_engine = AIEngine(feature_name='resume_parsing')

async def parse_resume_content(content: str) -> Optional[ResumeData]:
    """Parse resume text into structured data using core AI engine."""
    try:
        result = await ai_engine.generate(
            prompt=f"""Parse this resume content into structured sections:
{content}

Extract:
- Professional Summary
- Work Experience
- Education
- Skills
- Additional Sections""",
            output_type=ResumeData
        )
        
        if result:
            logger.info("Successfully parsed resume content")
            return result
            
        logger.error("Failed to parse resume content")
        return None
        
    except Exception as e:
        logger.error(f"Error parsing resume: {str(e)}")
        return None

def save_resume_data(data: ResumeData) -> bool:
    """Save parsed resume data to database using core session management."""
    try:
        with get_session() as session:
            # Save resume sections
            for name, content in data.sections.items():
                section = ResumeSection(
                    section_name=name,
                    content=content
                )
                session.add(section)
                
            # Save experiences
            for exp in data.experiences:
                experience = ResumeExperience(
                    company=exp.company,
                    title=exp.title,
                    start_date=exp.start_date,
                    end_date=exp.end_date,
                    location=exp.location,
                    description=exp.description
                )
                session.add(experience)
                
            # Save education
            for edu in data.education:
                education = ResumeEducation(
                    institution=edu.institution,
                    degree=edu.degree,
                    field=edu.field,
                    graduation_date=edu.graduation_date,
                    gpa=edu.gpa
                )
                session.add(education)
                
            session.commit()
            storage.sync_db()
            logger.info("Successfully saved resume data to database")
            return True
            
    except Exception as e:
        logger.error(f"Error saving resume data: {str(e)}")
        return False

async def main() -> int:
    """Main entry point for resume parsing."""
    try:
        # Get resume path
        inputs_dir = Path(__file__).parent.parent / "inputs"
        resume_path = inputs_dir / "Resume.pdf"
        if not resume_path.exists():
            logger.error(f"Resume not found at {resume_path}")
            logger.info(f"Please place your resume PDF in {inputs_dir}")
            return 1
            
        # Extract text using core PDF generator
        content = pdf_generator.extract_text(resume_path)
        if not content:
            logger.error("Failed to extract text from resume")
            return 1
            
        # Parse resume text
        logger.info("Parsing resume content...")
        parsed_data = await parse_resume_content(content)
        if not parsed_data:
            return 1
            
        # Save to database
        if save_resume_data(parsed_data):
            logger.info("Successfully processed resume")
            logger.info(f"- Found {len(parsed_data.experiences)} experiences")
            logger.info(f"- Found {len(parsed_data.education)} education entries")
            logger.info(f"- Found {len(parsed_data.sections)} additional sections")
            return 0
        else:
            logger.error("Failed to save resume data")
            return 1
            
    except Exception as e:
        logger.error(f"Error in resume processing: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))