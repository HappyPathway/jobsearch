"""PDF generation functionality."""
from pathlib import Path
import tempfile
from typing import Optional, Dict, Any
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader

from jobsearch.core.logging import setup_logging
from jobsearch.core.storage import GCSManager 
from jobsearch.core.database import get_session, JobApplication
from jobsearch.core.templates import TemplateManager

# Initialize core components
logger = setup_logging('pdf_generator')
storage = GCSManager()
templates = TemplateManager()

def setup_pdf_environment() -> bool:
    """Set up environment for PDF generation."""
    try:
        # Ensure templates are available
        required = ['resume.html', 'cover_letter.html', 'resume_visual.html']
        for template in required:
            if not templates.has_template(template):
                logger.error(f"Required template {template} not found")
                return False
        return True
    except Exception as e:
        logger.error(f"Error setting up PDF environment: {str(e)}")
        return False

async def update_document_metadata(application_id: int, **paths: Dict[str, str]) -> bool:
    """Update document metadata in database.
    
    Args:
        application_id: ID of the job application
        **paths: Dict of document types to file paths
        
    Returns:
        True if update was successful
    """
    try:
        with get_session() as session:
            application = session.query(JobApplication).get(application_id)
            if not application:
                logger.error(f"Application {application_id} not found")
                return False
                
            for doc_type, path in paths.items():
                setattr(application, f"{doc_type}_path", path)
                
            session.commit()
            storage.sync_db()
            return True
            
    except Exception as e:
        logger.error(f"Error updating document metadata: {str(e)}")
        return False
        
async def create_resume_pdf(content: str, output_path: str, application_id: Optional[int] = None) -> bool:
    """Generate PDF resume.
    
    Args:
        content: Resume content
        output_path: Path to save PDF
        application_id: Optional job application ID
        
    Returns:
        True if generation was successful
    """
    try:
        # Get resume template
        template = templates.get_template('resume.html')
        html = template.render(content=content)
        
        # Generate PDF
        HTML(string=html).write_pdf(
            output_path,
            stylesheets=[CSS(string=template.get_styles())]
        )
        
        # Update metadata if needed
        if application_id:
            await update_document_metadata(application_id, resume=output_path)
            
        return True
        
    except Exception as e:
        logger.error(f"Error creating resume PDF: {str(e)}")
        return False
        
async def create_cover_letter_pdf(
    content: str,
    job_info: Dict[str, Any],
    output_path: str,
    application_id: Optional[int] = None
) -> bool:
    """Generate PDF cover letter.
    
    Args:
        content: Cover letter content 
        job_info: Job details
        output_path: Path to save PDF
        application_id: Optional job application ID
        
    Returns:
        True if generation was successful
    """
    try:
        # Get cover letter template
        template = templates.get_template('cover_letter.html')
        html = template.render(
            content=content,
            job_title=job_info.get('title', ''),
            company=job_info.get('company', '')
        )
        
        # Generate PDF
        HTML(string=html).write_pdf(
            output_path,
            stylesheets=[CSS(string=template.get_styles())]
        )
        
        # Update metadata if needed
        if application_id:
            await update_document_metadata(application_id, cover_letter=output_path)
            
        return True
        
    except Exception as e:
        logger.error(f"Error creating cover letter PDF: {str(e)}")
        return False