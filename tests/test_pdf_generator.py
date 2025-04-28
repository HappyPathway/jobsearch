"""Test cases for the PDFGenerator class."""
import pytest
import tempfile
from pathlib import Path
from jobsearch.core.pdf import PDFGenerator

@pytest.fixture
def pdf_generator():
    return PDFGenerator()

def test_setup_environment(pdf_generator):
    """Test that PDF environment setup works."""
    assert pdf_generator.setup_environment() is True

def test_generate_from_text(pdf_generator):
    """Test generating a PDF from plain text."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        output_path = Path(temp_pdf.name)
        
        # Generate a PDF from test text
        result = pdf_generator.generate_from_text(
            text="Test content\nMultiple lines\nMore text",
            output_path=output_path,
            title="Test Document"
        )
        
        assert result is True
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        output_path.unlink()

def test_generate_pdf_with_template(pdf_generator):
    """Test generating a PDF from a template."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        output_path = Path(temp_pdf.name)
        
        # Test template and context
        template_content = """
        <!DOCTYPE html>
        <html>
        <head><title>{{ title }}</title></head>
        <body>
            <h1>{{ heading }}</h1>
            <p>{{ content }}</p>
        </body>
        </html>
        """
        
        context = {
            'title': 'Test Template',
            'heading': 'Hello World',
            'content': 'This is a test of the template system.'
        }
        
        # Store test template
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_template:
            temp_template.write(template_content)
            temp_template.flush()
            
            # Set up PDFGenerator with template directory
            generator = PDFGenerator(template_dir=Path(temp_template.name).parent)
            
            # Generate PDF from template
            result = generator.generate_pdf(
                template_name=Path(temp_template.name).name,
                context=context,
                output_path=output_path
            )
            
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 0
            
            # Clean up
            output_path.unlink()
            Path(temp_template.name).unlink()
            
def test_generate_resume_pdf(pdf_generator):
    """Test generating a resume PDF."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        output_path = Path(temp_pdf.name)
        
        # Mock resume content
        content = {
            'name': 'John Doe',
            'title': 'Software Engineer',
            'contact_info': {
                'email': 'john@example.com',
                'phone': '123-456-7890'
            },
            'summary': 'Experienced software engineer...',
            'experience': [
                {
                    'title': 'Senior Developer',
                    'company': 'Tech Corp',
                    'dates': '2020-Present',
                    'description': 'Led development team...'
                }
            ]
        }
        
        # Try both visual and ATS formats
        for visual in [True, False]:
            result = pdf_generator.generate_resume_pdf(
                content=content,
                output_path=output_path,
                visual=visual
            )
            
            assert result is True
            assert output_path.exists()
            assert output_path.stat().st_size > 0
            
            output_path.unlink()
            
def test_generate_cover_letter_pdf(pdf_generator):
    """Test generating a cover letter PDF."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        output_path = Path(temp_pdf.name)
        
        # Mock content
        content = {
            'greeting': 'Dear Hiring Manager,',
            'introduction': 'I am writing to express my interest...',
            'body': [
                'First paragraph...',
                'Second paragraph...'
            ],
            'closing': 'Thank you for your consideration.'
        }
        
        # Mock job info
        job_info = {
            'title': 'Senior Software Engineer',
            'company': 'Tech Corp',
            'location': 'New York, NY'
        }
        
        result = pdf_generator.generate_cover_letter_pdf(
            content=content,
            job_info=job_info,
            output_path=output_path,
            full_name='John Doe'
        )
        
        assert result is True
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        output_path.unlink()
        
def test_template_caching(pdf_generator):
    """Test that templates are properly cached."""
    template_name = 'test_template.html'
    template_content = '<html><body>Test template</body></html>'
    
    # Create a temporary template file
    with tempfile.TemporaryDirectory() as temp_dir:
        template_path = Path(temp_dir) / template_name
        template_path.write_text(template_content)
        
        # Create PDFGenerator with template directory
        generator = PDFGenerator(template_dir=temp_dir)
        
        # First load should read from file
        content1 = generator.get_template_content(template_name)
        assert content1 == template_content
        
        # Second load should use cache
        content2 = generator.get_template_content(template_name)
        assert content2 == template_content
        
        # Verify it's the same object in cache
        assert id(content1) == id(content2)
