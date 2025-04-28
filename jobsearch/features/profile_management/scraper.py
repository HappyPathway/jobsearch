"""Scrape and parse profile data from various sources."""
from pathlib import Path
from typing import Tuple, List, Dict, Optional, Set

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.models import Experience, Skill
from jobsearch.core.storage import GCSManager
from jobsearch.core.schemas import ProfileData, ExperienceData, SkillData
from jobsearch.core.pdf import PDFGenerator

# Initialize core components
logger = setup_logging('profile_scraper')
storage = GCSManager() 
pdf_generator = PDFGenerator()

def extract_text_from_pdf(file_path: Path) -> Optional[str]:
    """Extract text content from a PDF file using core PDFGenerator.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content or None if extraction fails
    """
    try:
        text = pdf_generator.extract_text(file_path)
        if not text:
            logger.error(f"No text extracted from PDF {file_path}")
            return None
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {str(e)}")
        return None

def parse_linkedin_pdf(pdf_path: Path) -> Tuple[List[ExperienceData], List[SkillData]]:
    """Parse LinkedIn profile PDF into experiences and skills.
    
    Args:
        pdf_path: Path to the LinkedIn profile PDF
        
    Returns:
        Tuple of (list of experience data, list of skills)
    """
    experiences: List[ExperienceData] = [] 
    skills: Set[str] = set()
    
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return [], []
        
    lines = text.split('\n')
    section = None
    current_exp = None
    
    # Pattern matching helper functions
    def is_section_header(line: str) -> bool:
        headers = ['experience', 'skills & endorsements', 'skills']
        return any(header in line.lower() for header in headers)
        
    def parse_date_range(line: str) -> Tuple[str, str]:
        """Extract start and end dates."""
        # Add date parsing logic...
        return '', ''
        
    for line in lines:
        line = line.strip()
        
        # Detect sections
        if is_section_header(line):
            section = 'skills' if 'skills' in line.lower() else 'experience'
            continue
            
        if section == 'experience':
            # Look for dates as they often indicate new experience
            date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|[0-9]{4}).*?-.*?(Present|[0-9]{4})', line)
            
            if date_match:
                # Save previous experience if exists
                if current_exp:
                    experiences.append(ExperienceData(
                        company=current_exp.get('company', 'Unknown'),
                        title=current_exp.get('title', 'Unknown'),
                        start_date=current_exp.get('start_date', ''),
                        end_date=current_exp.get('end_date', 'Present'),
                        description=current_exp.get('description', '')
                    ))
                current_exp = {'dates': line}
            elif current_exp:
                if 'title' not in current_exp:
                    current_exp['title'] = line
                elif 'company' not in current_exp:
                    current_exp['company'] = line
                elif 'description' not in current_exp:
                    current_exp['description'] = line
                else:
                    current_exp['description'] += f"\n{line}"
        
        elif section == 'skills':
            # Skip headers and common LinkedIn text 
            if line and not any(x in line.lower() for x in ['skills', 'endorsements', 'see more', 'show more']):
                # Clean and normalize skill text
                skill = re.sub(r'\([^)]*\)', '', line).strip()
                if skill and len(skill) > 1:
                    if ',' in skill:
                        # Handle comma-separated skills
                        for s in skill.split(','):
                            s = s.strip()
                            if s and len(s) > 1:
                                skills.add(s)
                    else:
                        skills.add(skill)

    # Add the last experience if any
    if current_exp:
        experiences.append(ExperienceData(
            company=current_exp.get('company', 'Unknown'),
            title=current_exp.get('title', 'Unknown'),
            start_date=current_exp.get('start_date', ''),
            end_date=current_exp.get('end_date', 'Present'),
            description=current_exp.get('description', '')
        ))

    # Convert skills to SkillData objects
    skill_objects = [SkillData(skill_name=skill) for skill in sorted(skills)]
    
    return experiences, skill_objects

def save_to_database(experiences: List[ExperienceData], skills: List[SkillData]) -> bool:
    """Save parsed profile data to the database using core database session.
    
    Args:
        experiences: List of experience data objects
        skills: List of skill data objects
        
    Returns:
        True if save was successful, False otherwise
    """
    try:
        with get_session() as session:
            # Save experiences
            for exp_data in experiences:
                experience = Experience(
                    company=exp_data.company,
                    title=exp_data.title,
                    start_date=exp_data.start_date,
                    end_date=exp_data.end_date,
                    description=exp_data.description
                )
                session.add(experience)
                
                # Save skills for experience
                for skill_data in skills:
                    skill = session.query(Skill).filter_by(skill_name=skill_data.skill_name).first()
                    if not skill:
                        skill = Skill(skill_name=skill_data.skill_name)
                        session.add(skill)
                    experience.skills.append(skill)
            
            session.commit()
            storage.sync_db()
            logger.info("Successfully saved profile data to database")
            return True
            
    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")
        return False

async def main() -> int:
    """Main entry point for LinkedIn profile scraping.
    
    Uses core components:
    - PDFGenerator for text extraction
    - Database session management for data storage 
    - GCS for cloud storage sync
    - Core logging for consistent log format
    
    Returns:
        0 on success, 1 on failure
    """
    try:
        # Ensure core services are available
        if not pdf_generator.is_initialized():
            logger.error("Core PDF generator not properly initialized")
            return 1
            
        # Get and validate input path
        inputs_dir = Path(__file__).parent.parent / "inputs"
        pdf_path = inputs_dir / "Profile.pdf"
        if not pdf_path.exists():
            logger.error(f"LinkedIn profile PDF not found at {pdf_path}")
            logger.info(f"Please place your LinkedIn profile PDF in {inputs_dir}")
            return 1
            
        # Extract text using core PDF generator
        logger.info(f"Extracting text from LinkedIn profile PDF: {pdf_path}")
        raw_text = pdf_generator.extract_text(pdf_path)
        if not raw_text:
            logger.error("Failed to extract text from profile PDF")
            return 1
            
        # Parse extracted text into structured data
        logger.info("Parsing LinkedIn profile content...")
        experiences, skills = parse_linkedin_pdf(pdf_path)
        if not experiences and not skills:
            logger.error("No data extracted from profile content. Please check PDF formatting.")
            return 1
            
        # Save to database using core session management
        logger.info("Saving parsed data using core database session...")
        if save_to_database(experiences, skills):
            logger.info(f"Successfully processed profile data:")
            logger.info(f"- Found {len(experiences)} experiences")
            logger.info(f"- Found {len(skills)} unique skills")
            logger.info("Profile data has been saved and synchronized to cloud storage")
            return 0
        else:
            logger.error("Failed to save data using core database session")
            return 1
            
    except Exception as e:
        logger.error("Unexpected error in profile processing", exc_info=True)
        return 1

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))