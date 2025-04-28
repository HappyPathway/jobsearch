"""PDF generation utilities for the job search platform."""
from pathlib import Path
import tempfile
from typing import Optional, Union, Dict, Any
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
from jobsearch.core.storage import GCSManager
from jobsearch.core.logging import setup_logging

# Initialize storage and logging
storage = GCSManager()
logger = setup_logging('pdf_generator')

class PDFGenerator:
    """Handles PDF generation from HTML templates and text content."""

    def __init__(self, template_dir: Optional[Union[str, Path]] = None):
        """Initialize PDF generator.
        
        Args:
            template_dir: Optional path to template directory. If not provided,
                        templates will be fetched from GCS.
        """
        self.template_dir = Path(template_dir) if template_dir else None
        self.templates_loaded = {}
        
    def get_template_content(self, template_name: str) -> Optional[str]:
        """Get template content from GCS or local directory.
        
        Args:
            template_name: Name of the template file
            
        Returns:
            Template content as string, or None if not found
        """
        if template_name in self.templates_loaded:
            return self.templates_loaded[template_name]

        if self.template_dir:
            template_path = self.template_dir / template_name
            if template_path.exists():
                content = template_path.read_text()
                self.templates_loaded[template_name] = content
                return content
        
        # Try GCS
        try:
            gcs_path = f'templates/{template_name}'
            if storage.file_exists(gcs_path):
                content = storage.download_as_string(gcs_path)
                self.templates_loaded[template_name] = content
                return content
        except Exception as e:
            logger.error(f"Error fetching template {template_name} from GCS: {str(e)}")
        
        return None

    def generate_pdf(
        self, 
        template_name: str,
        context: Dict[str, Any],
        output_path: Union[str, Path],
        css_string: Optional[str] = None
    ) -> bool:
        """Generate a PDF from a template and context.
        
        Args:
            template_name: Name of the HTML template file
            context: Dictionary of context variables for the template
            output_path: Path where to save the generated PDF
            css_string: Optional CSS string to apply
            
        Returns:
            True if PDF generation was successful, False otherwise
        """
        try:
            # Get template content
            template_content = self.get_template_content(template_name)
            if not template_content:
                logger.error(f"Template {template_name} not found")
                return False

            # Create temporary files for HTML generation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                
                # Create temporary HTML file
                temp_html = temp_dir_path / 'temp.html'
                
                # Set up Jinja environment
                env = Environment(loader=FileSystemLoader(str(temp_dir_path)))
                template = env.from_string(template_content)
                
                # Render template with context
                rendered_html = template.render(**context)
                temp_html.write_text(rendered_html)
                
                # Set up CSS
                css = CSS(string=css_string if css_string else '@page { margin: 1cm; }')
                
                # Generate PDF
                html = HTML(filename=str(temp_html))
                html.write_pdf(output_path, stylesheets=[css])
                
                return True
                
        except Exception as e:
            logger.error(f"Error generating PDF: {str(e)}")
            return False
    
    def generate_resume_pdf(
        self, 
        content: Dict[str, Any],
        output_path: Union[str, Path],
        visual: bool = False
    ) -> bool:
        """Generate a PDF resume.
        
        Args:
            content: Resume content dictionary
            output_path: Path to save the PDF
            visual: Whether to use the visual template
            
        Returns:
            True if successful, False otherwise
        """
        template = 'resume_visual.html' if visual else 'resume.html'
        return self.generate_pdf(template, {'content': content}, output_path)
    
    def generate_cover_letter_pdf(
        self,
        content: Dict[str, Any],
        job_info: Dict[str, Any],
        output_path: Union[str, Path],
        full_name: str = ""
    ) -> bool:
        """Generate a PDF cover letter.
        
        Args:
            content: Cover letter content dictionary
            job_info: Job information dictionary
            output_path: Path to save the PDF
            full_name: Optional name for the signature
            
        Returns:
            True if successful, False otherwise
        """
        context = {
            'content': content,
            'job_info': job_info,
            'full_name': full_name
        }
        return self.generate_pdf('cover_letter.html', context, output_path)

    def generate_from_text(
        self,
        text: str,
        output_path: Union[str, Path],
        title: Optional[str] = None,
        css_string: Optional[str] = None
    ) -> bool:
        """Generate a PDF from plain text.
        
        Args:
            text: Text content to convert to PDF
            output_path: Path to save the PDF
            title: Optional title for the document
            css_string: Optional CSS styling
            
        Returns:
            True if successful, False otherwise
        """
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                {f'<title>{title}</title>' if title else ''}
            </head>
            <body>
                <pre>{text}</pre>
            </body>
            </html>
            """
            
            # Create temporary files
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_html:
                temp_html_path = Path(temp_html.name)
                temp_html.write(html_content)
                
            # Generate PDF
            html = HTML(filename=str(temp_html_path))
            css = CSS(string=css_string if css_string else '@page { margin: 1cm; }')
            html.write_pdf(output_path, stylesheets=[css])
            
            # Cleanup
            temp_html_path.unlink()
            return True
            
        except Exception as e:
            logger.error(f"Error generating PDF from text: {str(e)}")
            return False
            
    @staticmethod
    def setup_environment() -> bool:
        """Verify that the PDF generation environment is properly set up.
        
        Returns:
            True if environment is ready for PDF generation
        """
        try:
            # Create a simple test PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as test_pdf:
                HTML(string="<p>Test</p>").write_pdf(test_pdf.name)
            return True
        except Exception as e:
            logger.error(f"PDF environment check failed: {str(e)}")
            return False
