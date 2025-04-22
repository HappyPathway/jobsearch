from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re
from datetime import datetime
from utils import session_scope
from models import (
    Experience, Skill, ResumeSection, ResumeExperience,
    ResumeEducation, CoverLetterSection, JobApplication,
    JobCache
)
from slugify import slugify
from pdf_generator import create_resume_pdf, create_cover_letter_pdf, setup_pdf_environment
from logging_utils import setup_logging
from structured_prompt import StructuredPrompt

# Import Slack notifier
try:
    from slack_notifier import get_notifier
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

logger = setup_logging('generate_documents')
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Check if Slack notifications are enabled by default
DEFAULT_SLACK_NOTIFICATIONS = os.getenv("ENABLE_SLACK_NOTIFICATIONS", "false").lower() in ["true", "1", "yes"]

# Initialize StructuredPrompt
structured_prompt = StructuredPrompt()

def get_profile_data():
    """Get all profile data from database using SQLAlchemy"""
    with session_scope() as session:
        # Get experiences with related skills using relationship
        experiences = session.query(Experience).order_by(
            Experience.end_date.desc(),
            Experience.start_date.desc()
        ).all()
        
        exp_list = [
            {
                "company": exp.company,
                "title": exp.title,
                "start_date": exp.start_date,
                "end_date": exp.end_date,
                "description": exp.description,
                "skills": [skill.skill_name for skill in exp.skills]  # Using the relationship
            }
            for exp in experiences
        ]
        
        # Get all unique skills
        skills = session.query(Skill.skill_name).distinct().all()
        skill_names = [skill[0] for skill in skills]
        
        # Get resume sections using a single query
        sections = dict(
            session.query(ResumeSection.section_name, ResumeSection.content)
            .all()
        )
        
        # Extract full name from contact info section more robustly
        contact_info = sections.get('Contact Information', '')
        full_name = ''
        if contact_info:
            # Try to get the first non-empty line as the name
            contact_lines = [line.strip() for line in contact_info.split('\n')]
            full_name = next((line for line in contact_lines if line), '')
        
        return exp_list, skill_names, sections, full_name

def create_job_directory(job_info):
    """Create a directory path for the job application in GCS"""
    logger.info(f"Creating directory for {job_info['title']} at {job_info['company']}")
    
    # Create base path for applications
    date_str = datetime.now().strftime("%Y-%m-%d")
    company_slug = slugify(job_info['company'])
    title_slug = slugify(job_info['title'])
    dir_name = f"{date_str}_{company_slug}_{title_slug}"
    
    # Return the GCS path prefix
    base_path = f"applications/{dir_name}"
    return Path(base_path)

def store_document(content, gcs_path, local_temp=None):
    """Store a document in GCS with optional local temp file
    
    Args:
        content (str): The content to store
        gcs_path (Path): The GCS path where to store the file
        local_temp (Path, optional): Local temp path if needed for PDF generation
    
    Returns:
        tuple: (gcs_path, local_temp_path if created else None)
    """
    from gcs_utils import gcs
    import tempfile
    
    # If we need a local temp file for processing
    if local_temp:
        local_temp.parent.mkdir(parents=True, exist_ok=True)
        with open(local_temp, 'w') as f:
            f.write(content)
        # Upload to GCS
        gcs.upload_file(local_temp, str(gcs_path))
        return str(gcs_path), local_temp
    else:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
            temp.write(content)
            temp_path = Path(temp.name)
        
        # Upload to GCS
        gcs.upload_file(temp_path, str(gcs_path))
        
        # Clean up temp file
        temp_path.unlink()
        return str(gcs_path), None

def get_document(gcs_path, local_path=None):
    """Get a document from GCS
    
    Args:
        gcs_path (str): The GCS path to retrieve
        local_path (Path, optional): Where to save the file locally if needed
    
    Returns:
        Path: Path to the local file if downloaded, None if file doesn't exist
    """
    from gcs_utils import gcs
    
    if local_path:
        if gcs.download_file(gcs_path, local_path):
            return local_path
    return None

def write_resume_with_gemini(resume_content):
    """Use Gemini with a specialized writing prompt to create engaging resume content"""
    prompt = f"""You are an expert resume writer. Take this structured resume content and write it as a polished, professional document.
Follow these rules:
1. Use clear, action-oriented language
2. Quantify achievements where possible
3. Maintain professional tone
4. Keep formatting minimal
5. Focus on relevance to the target role

Content to write:
{json.dumps(resume_content, indent=2)}

Write a complete, properly formatted resume. Use standard section headers and bullet points.
Do not return JSON or any other structured format - just return the formatted text of the resume."""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.2,
            }
        )
        
        return response.text.strip()
            
    except Exception as e:
        logger.error(f"Error in resume writing pass: {str(e)}")
        return None

def write_cover_letter_with_gemini(cover_letter_content, job_info):
    """Use Gemini with a specialized writing prompt to create an engaging cover letter"""
    prompt = f"""You are an expert cover letter writer. Take this structured content and write it as a compelling letter FROM the job applicant TO the hiring manager.
Follow these rules:
1. Write FROM the applicant perspective (never address the letter to the applicant)
2. Maintain professional but engaging tone
3. Show enthusiasm and personality
4. Connect experience to job requirements
5. Keep paragraphs focused and concise
6. End with a clear call to action
7. Include a proper signature line

Job Details:
{json.dumps(job_info, indent=2)}

Content to write:
{json.dumps(cover_letter_content, indent=2)}

Write a complete, properly formatted cover letter, including greeting, body, and signature.
Do not return JSON or any other structured format - just return the formatted text of the letter."""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1500,
                "temperature": 0.3,
            }
        )
        
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error in cover letter writing pass: {str(e)}")
        return None

def format_resume(content):
    """Format resume content into a presentable text document"""
    sections = [
        f"## Professional Summary\n\n{content['summary']}\n",
        "## Professional Experience\n"
    ]
    
    for exp in content['selected_experiences']:
        sections.append(f"""
* **{exp['title']}** at **{exp['company']}** ({exp['dates']})
{exp['description']}
""".strip())
    
    sections.append("\n## Technical Skills\n")
    sections.extend([f"* {skill}" for skill in content['highlighted_skills']])
    
    for name, content in content['additional_sections'].items():
        sections.append(f"\n## {name}\n\n{content}")
    
    return "\n\n".join(sections)

def format_cover_letter(content, job_info):
    """Format cover letter content into a presentable text document"""
    sections = [
        content['greeting'],
        content['opening'],
    ]
    
    sections.extend(content['body_paragraphs'])
    sections.append(content['closing'])
    sections.append(content['signature'])
    
    return "\n\n".join(sections)

def generate_tailored_resume(job_info, experiences, skills, sections):
    """Generate tailored resume content based on job requirements"""
    try:
        # Define expected structure
        expected_structure = {
            "summary": str,
            "selected_experiences": [{
                "company": str,
                "title": str,
                "start_date": str,
                "end_date": str,
                "description": str,
                "achievements": [str]
            }],
            "highlighted_skills": [str],
            "additional_sections": {
                "certifications": [str],
                "education": [str],
                "projects": [str]
            }
        }

        # Example data
        example_data = {
            "summary": "Senior technology leader with expertise in cloud architecture and DevOps transformation...",
            "selected_experiences": [{
                "company": "Tech Corp",
                "title": "Senior Software Engineer",
                "start_date": "2020-01",
                "end_date": "Present",
                "description": "Led development of cloud infrastructure",
                "achievements": [
                    "Reduced deployment time by 75%",
                    "Implemented CI/CD pipeline"
                ]
            }],
            "highlighted_skills": ["Python", "AWS", "Kubernetes"],
            "additional_sections": {
                "certifications": ["AWS Solutions Architect"],
                "education": ["BS Computer Science"],
                "projects": ["Cloud Migration"]
            }
        }

        # Get structured response
        resume_content = structured_prompt.get_structured_response(
            prompt=f"""Using the provided experiences and skills, create a resume optimized for this job.

Job Information:
{json.dumps(job_info, indent=2)}

Available Experiences:
{json.dumps(experiences, indent=2)}

Skills:
{json.dumps(skills, indent=2)}

Instructions:
1. Select and prioritize experiences most relevant to the job
2. Highlight skills that match job requirements
3. Maintain chronological order
4. Include key achievements
5. Keep descriptions concise and impactful""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if resume_content:
            logger.info("Successfully generated tailored resume content")
            return resume_content

        logger.error("Failed to generate resume content")
        return None

    except Exception as e:
        logger.error(f"Error generating resume content: {str(e)}")
        return None

def generate_cover_letter(job_info, resume_content, skills, full_name=""):
    """Generate cover letter content matching the resume"""
    try:
        # Define expected structure
        expected_structure = {
            "greeting": str,
            "opening": str,
            "body_paragraphs": [str],
            "closing": str,
            "signature": str
        }

        # Example data
        example_data = {
            "greeting": "Dear Hiring Manager,",
            "opening": "I am writing to express my strong interest in the Senior Software Engineer position...",
            "body_paragraphs": [
                "With over 8 years of experience in cloud infrastructure...",
                "In my current role at Tech Corp, I have successfully..."
            ],
            "closing": "I am excited about the opportunity to contribute...",
            "signature": "Sincerely,\nJohn Doe"
        }

        # Get structured response
        cover_letter_content = structured_prompt.get_structured_response(
            prompt=f"""Create a compelling cover letter that matches the resume and targets this specific job.

Job Details:
{json.dumps(job_info, indent=2)}

Resume Content:
{json.dumps(resume_content, indent=2)}

Skills:
{json.dumps(skills, indent=2)}

Instructions:
1. Write FROM the applicant's perspective
2. Maintain professional but engaging tone
3. Show enthusiasm and personality
4. Connect experience to job requirements
5. Keep paragraphs focused and concise
6. End with a clear call to action
7. Add a professional signature block that says "Sincerely," followed by the applicant's name (use "{full_name}" if provided, otherwise use "Sincerely," only)""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if cover_letter_content:
            logger.info("Successfully generated cover letter content")
            return cover_letter_content

        logger.error("Failed to generate cover letter content")
        return None

    except Exception as e:
        logger.error(f"Error generating cover letter content: {str(e)}")
        return None

def track_job_application(job_info, resume_path, cover_letter_path):
    """Track job application in the database"""
    with session_scope() as session:
        # First, ensure job exists in cache
        job = session.query(JobCache).filter_by(url=job_info.get('url', '')).first()
        if not job:
            # Create new job cache entry
            job = JobCache(
                url=job_info.get('url', ''),
                title=job_info['title'],
                company=job_info['company'],
                description=job_info.get('description', ''),
                first_seen_date=datetime.now().isoformat(),
                last_seen_date=datetime.now().isoformat(),
                match_score=job_info.get('match_score', 0.0),
                application_priority=job_info.get('application_priority', 'low'),
                key_requirements=json.dumps(job_info.get('key_requirements', [])),
                culture_indicators=json.dumps(job_info.get('culture_indicators', [])),
                career_growth_potential=job_info.get('career_growth_potential', '')
            )
            session.add(job)
            session.flush()  # To get the job.id
        
        # Create or update application record
        application = session.query(JobApplication).filter_by(job_cache_id=job.id).first()
        if not application:
            application = JobApplication(
                job_cache_id=job.id,
                application_date=datetime.now().isoformat(),
                status='documents_generated',
                resume_path=resume_path,
                cover_letter_path=cover_letter_path,
                notes='Initial documents generated'
            )
            session.add(application)
        else:
            application.resume_path = resume_path
            application.cover_letter_path = cover_letter_path
            application.notes += f"\nDocuments regenerated on {datetime.now().isoformat()}"
        
        return job.id, application.id

def generate_readme_markdown(job_info):
    """Generate markdown content for README.md"""
    return f"""# Job Application: {job_info['title']} at {job_info['company']}

## Job Details
- **Title**: {job_info['title']}
- **Company**: {job_info['company']}
- **URL**: {job_info.get('url', 'N/A')}
- **Description**: {job_info.get('description', 'N/A')}
- **Match Score**: {job_info.get('match_score', 0)}
- **Application Priority**: {job_info.get('application_priority', 'low')}
- **Key Requirements**: {', '.join(job_info.get('key_requirements', []))}
- **Culture Indicators**: {', '.join(job_info.get('culture_indicators', []))}
- **Career Growth Potential**: {job_info.get('career_growth_potential', 'N/A')}
- **Generated Date**: {datetime.now().isoformat()}
"""

def generate_job_documents(job_info, use_writing_pass=True, use_visual_resume=True, send_slack=DEFAULT_SLACK_NOTIFICATIONS):
    """Generate both resume and cover letter for a specific job"""
    logger.info(f"Generating documents for {job_info['title']} at {job_info['company']}")
    
    try:
        # Get profile data using our improved function
        exp_list, skills, sections, full_name = get_profile_data()
        
        # First pass: Generate structured content with StructuredPrompt
        resume_content = generate_tailored_resume(job_info, exp_list, skills, sections)
        if not resume_content:
            logger.error("Failed to generate resume content")
            return None, None
            
        # Second pass: Optional writing enhancement with Gemini
        if use_writing_pass:
            resume_text = write_resume_with_gemini(resume_content)
            if not resume_text:
                logger.warning("Writing pass failed, falling back to standard format")
                resume_text = format_resume(resume_content)
        else:
            resume_text = format_resume(resume_content)
        
        # Generate matching cover letter content
        cover_letter_content = generate_cover_letter(job_info, resume_content, skills, full_name)
        if not cover_letter_content:
            logger.error("Failed to generate cover letter content")
            return None, None
            
        # Optional writing enhancement for cover letter
        if use_writing_pass:
            cover_letter_text = write_cover_letter_with_gemini(cover_letter_content, job_info)
            if not cover_letter_text:
                logger.warning("Cover letter writing pass failed, falling back to standard format")
                cover_letter_text = format_cover_letter(cover_letter_content, job_info)
        else:
            cover_letter_text = format_cover_letter(cover_letter_content, job_info)
        
        # Create job directory path in GCS
        job_dir = create_job_directory(job_info)
        
        # Create temporary directory for PDF generation
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Store text versions in GCS
            resume_txt_gcs_path = job_dir / "resume.txt"
            cover_letter_txt_gcs_path = job_dir / "cover_letter.txt"
            readme_gcs_path = job_dir / "README.md"
            
            # Store text files
            store_document(resume_text, resume_txt_gcs_path)
            store_document(cover_letter_text, cover_letter_txt_gcs_path)
            store_document(generate_readme_markdown(job_info), readme_gcs_path)
            
            # Define PDF paths
            default_resume_pdf_path = job_dir / "resume.pdf"
            ats_resume_pdf_path = job_dir / "resume_ats.pdf"
            visual_resume_pdf_path = job_dir / "resume_visual.pdf"
            cover_letter_pdf_path = job_dir / "cover_letter.pdf"
            
            # Local temp paths for PDF generation
            temp_ats_pdf = temp_dir_path / "resume_ats.pdf"
            temp_visual_pdf = temp_dir_path / "resume_visual.pdf"
            temp_cover_letter_pdf = temp_dir_path / "cover_letter.pdf"
            
            if setup_pdf_environment():
                try:
                    # Create ATS-friendly resume
                    create_resume_pdf(resume_content, str(temp_ats_pdf))
                    store_document("", ats_resume_pdf_path, temp_ats_pdf)
                    
                    # Create visual resume if requested
                    if use_visual_resume:
                        from pdf_generator import create_visual_resume_pdf
                        create_visual_resume_pdf(resume_content, str(temp_visual_pdf))
                        store_document("", visual_resume_pdf_path, temp_visual_pdf)
                        
                        # Set default resume to visual version
                        shutil.copy(temp_visual_pdf, temp_dir_path / "resume.pdf")
                        store_document("", default_resume_pdf_path, temp_dir_path / "resume.pdf")
                    else:
                        # Set default resume to ATS version
                        shutil.copy(temp_ats_pdf, temp_dir_path / "resume.pdf")
                        store_document("", default_resume_pdf_path, temp_dir_path / "resume.pdf")
                    
                    # Create cover letter
                    create_cover_letter_pdf(cover_letter_content, job_info, str(temp_cover_letter_pdf), full_name)
                    store_document("", cover_letter_pdf_path, temp_cover_letter_pdf)
                    
                    logger.info("Successfully generated and stored PDF documents in GCS")
                except Exception as e:
                    logger.error(f"Error generating PDF documents: {str(e)}")
                    default_resume_pdf_path = resume_txt_gcs_path
                    cover_letter_pdf_path = cover_letter_txt_gcs_path
            else:
                logger.warning("PDF environment not available, using text versions only")
                default_resume_pdf_path = resume_txt_gcs_path
                cover_letter_pdf_path = cover_letter_txt_gcs_path
            
            # Track job application in the database - use default resume as the main resume
            job_id, application_id = track_job_application(job_info, str(default_resume_pdf_path), str(cover_letter_pdf_path))
            
            logger.info(f"Successfully generated documents in GCS at {job_dir}")
            
            # Send Slack notification if enabled
            if send_slack and SLACK_AVAILABLE:
                try:
                    logger.info("Sending Slack notification about generated documents")
                    notifier = get_notifier()
                    notifier.send_job_application_notification(
                        job_info, 
                        str(default_resume_pdf_path), 
                        str(cover_letter_pdf_path)
                    )
                except Exception as e:
                    logger.error(f"Error sending Slack notification: {str(e)}")
            
            # Return paths to the main resume and cover letter in GCS
            return str(default_resume_pdf_path), str(cover_letter_pdf_path)
        
    except Exception as e:
        logger.error(f"Error generating job documents: {str(e)}")
        return None, None

def main():
    """Main entry point for document generation"""
    import argparse
    parser = argparse.ArgumentParser(description='Generate tailored resume and cover letter')
    parser.add_argument('job_info_path', help='Path to job details JSON file or GCS path (e.g. jobs/2025-04-22/job.json)')
    parser.add_argument('--no-writing-pass', action='store_true', 
                      help='Skip the writing enhancement pass')
    parser.add_argument('--no-visual-resume', action='store_false', dest='use_visual_resume',
                      help='Skip generating the visual resume (only generate ATS-friendly version)')
    parser.add_argument('--ats-only', action='store_false', dest='use_visual_resume',
                      help='Only generate the ATS-friendly resume (synonym for --no-visual-resume)')
    parser.add_argument('--no-slack', action='store_false', dest='send_slack',
                      help='Disable Slack notifications')
    parser.set_defaults(use_visual_resume=True, send_slack=DEFAULT_SLACK_NOTIFICATIONS)
    args = parser.parse_args()

    try:
        # Check if path is a GCS path or local file
        if '/' in args.job_info_path and not os.path.exists(args.job_info_path):
            # Try to get from GCS
            content = gcs.safe_download(args.job_info_path)
            if not content:
                logger.error(f"Could not find job info in GCS at {args.job_info_path}")
                return 1
            job_info = json.loads(content)
        else:
            # Load from local file
            if not os.path.exists(args.job_info_path):
                logger.error(f"Job info file not found: {args.job_info_path}")
                return 1
            with open(args.job_info_path, 'r') as f:
                job_info = json.load(f)
        
        # Generate documents
        resume_path, cover_letter_path = generate_job_documents(
            job_info, 
            use_writing_pass=not args.no_writing_pass,
            use_visual_resume=args.use_visual_resume,
            send_slack=args.send_slack
        )
        
        if resume_path and cover_letter_path:
            print(f"Successfully generated documents:")
            print(f"Resume: {resume_path}")
            if args.use_visual_resume:
                visual_resume_path = str(Path(resume_path).parent / "resume_visual.pdf")
                ats_resume_path = str(Path(resume_path).parent / "resume_ats.pdf")
                print(f"Visual Resume: {visual_resume_path}")
                print(f"ATS-friendly Resume: {ats_resume_path}")
            print(f"Cover Letter: {cover_letter_path}")
            return 0
        else:
            print("Failed to generate documents")
            return 1
    except Exception as e:
        logger.error(f"Error generating documents: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main())