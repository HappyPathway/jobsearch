from weasyprint import HTML, CSS
from pathlib import Path
import datetime
from jinja2 import Environment, FileSystemLoader
import os
from sqlalchemy.orm import Session
from models import JobApplication, JobCache
from datetime import datetime

# Set up Jinja2 environment for HTML templates
template_dir = Path(__file__).parent / 'templates'
template_dir.mkdir(exist_ok=True)

def setup_templates():
    """Create HTML templates if they don't exist"""
    # Resume template
    resume_template = template_dir / 'resume.html'
    if not resume_template.exists():
        resume_template.write_text('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: letter;
            margin: 1in;
        }
        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            line-height: 1.4;
            color: #333;
        }
        h1 {
            text-align: center;
            color: #2c3e50;
            font-size: 24px;
            margin-bottom: 20px;
        }
        .section {
            margin-bottom: 20px;
        }
        .section-title {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            font-size: 18px;
            margin-bottom: 10px;
            padding-bottom: 5px;
        }
        .experience-item {
            margin-bottom: 15px;
        }
        .job-title {
            font-weight: bold;
            color: #34495e;
        }
        .company {
            font-weight: bold;
        }
        .dates {
            color: #7f8c8d;
            font-style: italic;
        }
        .description {
            margin-top: 5px;
            padding-left: 20px;
        }
        .description ul {
            margin: 5px 0;
            padding-left: 20px;
        }
        .skills {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .skill {
            background-color: #f6f8fa;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <h1>PROFESSIONAL RESUME</h1>
    
    <div class="section">
        <div class="section-title">PROFESSIONAL SUMMARY</div>
        <div>{{ summary }}</div>
    </div>

    <div class="section">
        <div class="section-title">PROFESSIONAL EXPERIENCE</div>
        {% for exp in experiences %}
        <div class="experience-item">
            <div>
                <span class="job-title">{{ exp.title }}</span> - 
                <span class="company">{{ exp.company }}</span>
            </div>
            <div class="dates">{{ exp.dates }}</div>
            <div class="description">
                {% if exp.description is string %}
                    {{ exp.description }}
                {% else %}
                    <ul>
                    {% for bullet in exp.description %}
                        <li>{{ bullet }}</li>
                    {% endfor %}
                    </ul>
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>

    <div class="section">
        <div class="section-title">TECHNICAL SKILLS</div>
        <div class="skills">
            {% for skill in skills %}
            <span class="skill">{{ skill }}</span>
            {% endfor %}
        </div>
    </div>

    {% for section_name, content in additional_sections.items() %}
    <div class="section">
        <div class="section-title">{{ section_name | upper }}</div>
        <div>{{ content }}</div>
    </div>
    {% endfor %}
</body>
</html>
        ''')

    # Cover Letter template
    cover_letter_template = template_dir / 'cover_letter.html'
    if not cover_letter_template.exists():
        cover_letter_template.write_text('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: letter;
            margin: 1in;
        }
        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            line-height: 1.6;
            color: #333;
        }
        .date {
            margin-bottom: 20px;
        }
        .company {
            margin-bottom: 5px;
        }
        .subject {
            margin-bottom: 20px;
            font-weight: bold;
        }
        .greeting {
            margin-bottom: 20px;
        }
        .content p {
            margin-bottom: 15px;
            text-align: justify;
        }
        .closing {
            margin-top: 30px;
            margin-bottom: 10px;
        }
        .signature {
            margin-top: 40px;
        }
    </style>
</head>
<body>
    <div class="date">{{ date }}</div>
    
    <div class="company">{{ company }}</div>
    <div class="subject">Re: Application for {{ title }}</div>

    <div class="greeting">{{ greeting }}</div>

    <div class="content">
        <p>{{ opening }}</p>
        
        {% for paragraph in body_paragraphs %}
        <p>{{ paragraph }}</p>
        {% endfor %}
    </div>

    <div class="closing">{{ closing }}</div>
    <div class="signature">{{ signature }}</div>
</body>
</html>
        ''')

def update_document_metadata(application_id, resume_path=None, cover_letter_path=None):
    """Update document metadata in the database"""
    with Session() as session:
        application = session.query(JobApplication).get(application_id)
        if not application:
            return False
            
        if resume_path:
            application.resume_path = resume_path
        if cover_letter_path:
            application.cover_letter_path = cover_letter_path
            
        application.last_modified = datetime.now().isoformat()
        session.commit()
        return True

def create_resume_pdf(content, output_path, application_id=None):
    """Generate a professional PDF resume using HTML/CSS"""
    setup_templates()
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('resume.html')
    
    # Prepare template data
    data = {
        'summary': content['summary'],
        'experiences': sorted(
            content['selected_experiences'], 
            key=lambda x: x.get('relevance_score', 0), 
            reverse=True
        ),
        'skills': content['highlighted_skills'],
        'additional_sections': content.get('additional_sections', {})
    }
    
    try:
        # Render HTML
        html_content = template.render(**data)
        
        # Generate PDF
        HTML(string=html_content).write_pdf(output_path)
        
        if application_id:
            update_document_metadata(application_id, resume_path=f"{output_path}.pdf")
            
    except Exception as e:
        logger.error(f"Error creating resume PDF: {str(e)}")
        raise

def create_cover_letter_pdf(content, job_info, output_path, application_id=None):
    """Generate a professional PDF cover letter using HTML/CSS"""
    setup_templates()
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('cover_letter.html')
    
    # Prepare template data
    data = {
        'date': datetime.date.today().strftime("%B %d, %Y"),
        'company': job_info['company'],
        'title': job_info['title'],
        'greeting': content['greeting'],
        'opening': content['opening'],
        'body_paragraphs': content['body_paragraphs'],
        'closing': content['closing'],
        'signature': content['signature'].replace('\\n', '\n')
    }
    
    try:
        # Render HTML
        html_content = template.render(**data)
        
        # Generate PDF
        HTML(string=html_content).write_pdf(output_path)
        
        if application_id:
            update_document_metadata(application_id, cover_letter_path=f"{output_path}.pdf")
            
    except Exception as e:
        logger.error(f"Error creating cover letter PDF: {str(e)}")
        raise

def setup_pdf_environment():
    """Check if WeasyPrint and its dependencies are installed"""
    try:
        import weasyprint
        return True
    except ImportError as e:
        print(f"Error: WeasyPrint not installed: {str(e)}")
        return False
    except Exception as e:
        print(f"Error setting up PDF environment: {str(e)}")
        return False