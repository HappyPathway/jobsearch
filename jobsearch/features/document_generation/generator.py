"""Document generation module using core libraries."""
from pathlib import Path
from typing import Optional, Tuple, Dict
from datetime import datetime

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import get_session
from jobsearch.core.models import (
    Experience, Skill, ResumeSection, 
    CoverLetterSection, JobCache, JobApplication
)
from jobsearch.core.storage import GCSManager
from jobsearch.core.ai import AIEngine
from jobsearch.core.markdown import MarkdownGenerator
from jobsearch.core.pdf import PDFGenerator
from jobsearch.core.schemas import ResumeContent, CoverLetterContent

# Initialize core components
logger = setup_logging('document_generator')
storage = GCSManager()
ai_engine = AIEngine(feature_name='document_generation')
markdown = MarkdownGenerator()
pdf_generator = PDFGenerator()

async def generate_resume(job_data: Dict, experiences: list, skills: list, sections: Dict) -> Optional[str]:
    """Generate a tailored resume using core AI Engine."""
    try:
        result = await ai_engine.generate(
            prompt=f"""Generate a tailored resume for:
Job Title: {job_data.get('title')}
Company: {job_data.get('company')}
Description: {job_data.get('description')}

Based on:
{markdown.format_experiences(experiences)}

Skills:
{markdown.format_skills(skills)}

Additional Sections:
{markdown.format_sections(sections)}
""",
            output_type=ResumeContent
        )
        
        if result:
            # Format resume content
            content = markdown.format_resume(
                summary=result.summary,
                experience=result.experience,
                skills=result.skills,
                additional=result.additional_sections
            )
            
            # Generate PDF
            company = job_data.get('company', '').lower().replace(' ', '_')
            pdf_path = f'resumes/{company}_{datetime.now().strftime("%Y%m%d")}.pdf'
            
            if pdf_generator.create_pdf(content, pdf_path):
                logger.info(f"Generated resume at {pdf_path}")
                return pdf_path
                
        logger.error("Failed to generate resume")
        return None
        
    except Exception as e:
        logger.error(f"Error generating resume: {str(e)}")
        return None

async def generate_cover_letter(job_data: Dict, resume_content: str) -> Optional[str]:
    """Generate a matching cover letter using core AI Engine."""
    try:
        result = await ai_engine.generate(
            prompt=f"""Generate a cover letter matching:
Job Details:
{job_data.get('title')} at {job_data.get('company')}
{job_data.get('description')}

Based on Resume:
{resume_content}
""",
            output_type=CoverLetterContent
        )
        
        if result:
            # Format cover letter
            content = markdown.format_cover_letter(
                greeting=result.greeting,
                introduction=result.introduction,
                body=result.body,
                closing=result.closing,
                signature=result.signature
            )
            
            # Generate PDF
            company = job_data.get('company', '').lower().replace(' ', '_')
            pdf_path = f'cover_letters/{company}_{datetime.now().strftime("%Y%m%d")}.pdf'
            
            if pdf_generator.create_pdf(content, pdf_path):
                logger.info(f"Generated cover letter at {pdf_path}")
                return pdf_path
                
        logger.error("Failed to generate cover letter")
        return None
        
    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
        return None

async def generate_job_documents(job_data: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Generate all documents for a job application."""
    try:
        # Get profile data
        with get_session() as session:
            experiences = session.query(Experience).order_by(Experience.end_date.desc()).all()
            skills = session.query(Skill).all()
            sections = dict(session.query(ResumeSection.section_name, ResumeSection.content).all())
        
        # Generate resume
        resume_path = await generate_resume(job_data, experiences, skills, sections)
        if not resume_path:
            return None, None
            
        # Get resume content for cover letter
        resume_content = storage.read_file(resume_path)
        if not resume_content:
            logger.error("Could not read resume content")
            return None, None
            
        # Generate cover letter
        cover_letter_path = await generate_cover_letter(job_data, resume_content)
        if not cover_letter_path:
            return None, None
            
        # Track in database
        with get_session() as session:
            # Ensure job exists in cache
            job = session.query(JobCache).filter_by(url=job_data.get('url')).first()
            if not job:
                job = JobCache(
                    url=job_data.get('url'),
                    title=job_data.get('title'),
                    company=job_data.get('company'),
                    description=job_data.get('description', ''),
                    first_seen_date=datetime.now().isoformat()
                )
                session.add(job)
                
            # Create/update application
            application = JobApplication(
                job_cache_id=job.id,
                resume_path=resume_path,
                cover_letter_path=cover_letter_path,
                status='documents_generated',
                application_date=datetime.now().isoformat()
            )
            session.add(application)
            session.commit()
            
        return resume_path, cover_letter_path
        
    except Exception as e:
        logger.error(f"Error generating documents: {str(e)}")
        return None, None

async def main() -> int:
    """Main entry point for document generation."""
    try:
        import json
        import sys
        
        if len(sys.argv) < 2:
            logger.error("Usage: generator.py <job_data.json>")
            return 1
            
        # Load job data
        with open(sys.argv[1]) as f:
            job_data = json.load(f)
            
        resume_path, cover_letter_path = await generate_job_documents(job_data)
        
        if resume_path and cover_letter_path:
            logger.info("Successfully generated documents:")
            logger.info(f"Resume: {resume_path}")
            logger.info(f"Cover Letter: {cover_letter_path}")
            return 0
        else:
            logger.error("Failed to generate documents")
            return 1
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))