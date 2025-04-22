from weasyprint import HTML, CSS
from pathlib import Path
import datetime as dt
from jinja2 import Environment, FileSystemLoader
import os
import tempfile
from sqlalchemy.orm import Session
from models import JobApplication, JobCache
from logging_utils import setup_logging
from gcs_utils import gcs

logger = setup_logging('pdf_generator')

def get_template_content(template_name):
    """Get template content from GCS or create if doesn't exist"""
    try:
        template_path = f'templates/{template_name}'
        content = gcs.safe_download(template_path)
        if not content:
            logger.warning(f"Template {template_name} not found in GCS")
            return None
        return content
    except Exception as e:
        logger.error(f"Error getting template {template_name}: {str(e)}")
        return None

def store_template_content(template_name, content):
    """Store template content in GCS"""
    try:
        template_path = f'templates/{template_name}'
        if gcs.safe_upload(content, template_path):
            logger.info(f"Successfully stored template {template_name}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error storing template {template_name}: {str(e)}")
        return False

def setup_pdf_environment():
    """Set up environment for PDF generation"""
    try:
        # Ensure templates are available
        templates = ['resume.html', 'cover_letter.html', 'visual_resume.html']
        for template in templates:
            content = get_template_content(template)
            if not content:
                logger.error(f"Required template {template} not found")
                return False
        return True
    except Exception as e:
        logger.error(f"Error setting up PDF environment: {str(e)}")
        return False

def update_document_metadata(application_id, resume_path=None, cover_letter_path=None):
    """Update document metadata in the database"""
    with Session() as session:
        application = session.query(JobApplication).get(application_id)
        if not application:
            return False
            
        if resume_path:
            # Ensure path ends with .pdf
            resume_path = str(resume_path)
            if not resume_path.endswith('.pdf'):
                resume_path += '.pdf'
            application.resume_path = resume_path
            
        if cover_letter_path:
            # Ensure path ends with .pdf
            cover_letter_path = str(cover_letter_path)
            if not cover_letter_path.endswith('.pdf'):
                cover_letter_path += '.pdf'
            application.cover_letter_path = cover_letter_path
            
        application.last_modified = dt.datetime.now().isoformat()
        session.commit()
        return True

def create_resume_pdf(content, output_path, application_id=None):
    """Generate a professional PDF resume using HTML/CSS"""
    try:
        # Get template content from GCS
        template_content = get_template_content('resume.html')
        if not template_content:
            raise Exception("Resume template not found")

        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_html:
            temp_html_path = Path(temp_html.name)
            
            # Set up Jinja environment with temporary directory
            temp_dir = temp_html_path.parent
            env = Environment(loader=FileSystemLoader(str(temp_dir)))
            
            # Write template to temp file
            temp_html.write(template_content)
            temp_html.flush()
            
            # Create PDF using WeasyPrint
            html = HTML(filename=str(temp_html_path))
            css = CSS(string='@page { margin: 1cm; }')
            html.write_pdf(output_path, stylesheets=[css])
            
            # Clean up temp file
            temp_html_path.unlink()
            
            if application_id:
                update_document_metadata(application_id, resume_path=output_path)
                
            return True
    except Exception as e:
        logger.error(f"Error creating resume PDF: {str(e)}")
        return False

def create_cover_letter_pdf(content, job_info, output_path, full_name="", application_id=None):
    """Generate a professional PDF cover letter using HTML/CSS"""
    try:
        # Get template content from GCS
        template_content = get_template_content('cover_letter.html')
        if not template_content:
            raise Exception("Cover letter template not found")

        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_html:
            temp_html_path = Path(temp_html.name)
            
            # Set up Jinja environment with temporary directory
            temp_dir = temp_html_path.parent
            env = Environment(loader=FileSystemLoader(str(temp_dir)))
            
            # Write template to temp file
            temp_html.write(template_content)
            temp_html.flush()
            
            # Create PDF using WeasyPrint
            html = HTML(filename=str(temp_html_path))
            css = CSS(string='@page { margin: 1cm; }')
            html.write_pdf(output_path, stylesheets=[css])
            
            # Clean up temp file
            temp_html_path.unlink()
            
            if application_id:
                update_document_metadata(application_id, cover_letter_path=output_path)
                
            return True
    except Exception as e:
        logger.error(f"Error creating cover letter PDF: {str(e)}")
        return False