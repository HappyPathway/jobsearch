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
    """Create a directory for the job application"""
    logger.info(f"Creating directory for {job_info['title']} at {job_info['company']}")
    
    # Create applications directory if it doesn't exist
    base_dir = Path(__file__).parent.parent / 'applications'
    base_dir.mkdir(exist_ok=True)
    
    # Create directory name from date and company
    date_str = datetime.now().strftime("%Y-%m-%d")
    company_slug = slugify(job_info['company'])
    title_slug = slugify(job_info['title'])
    dir_name = f"{date_str}_{company_slug}_{title_slug}"
    
    job_dir = base_dir / dir_name
    job_dir.mkdir(exist_ok=True)
    
    return job_dir

def write_resume_with_gemini(resume_content):
    """Use Gemini with a specialized writing prompt to create engaging resume content"""
    prompt = f"""You are an expert resume writer. Take this structured resume content and write it as a polished, professional document.
Follow these rules:
1. Use clear, action-oriented language
2. Quantify achievements where possible
3. Maintain professional tone
4. Keep formatting minimal - no special characters or styling
5. Focus on relevance to the target role

Content to write:
{json.dumps(resume_content, indent=2)}

Format the output as a plain text document with sections clearly marked."""

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
    prompt = f"""You are an expert cover letter writer. Take this structured content and write it as a compelling letter.
Follow these rules:
1. Maintain professional but engaging tone
2. Show enthusiasm and personality
3. Connect experience to job requirements
4. Keep paragraphs focused and concise
5. End with a clear call to action

Job Details:
{json.dumps(job_info, indent=2)}

Content to write:
{json.dumps(cover_letter_content, indent=2)}

Format the output as a plain text letter."""

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
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""You are an expert resume tailoring system. Using the provided experiences and skills, create a resume optimized for this job.

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
5. Keep descriptions concise and impactful

Return a JSON object with:
- summary: Professional summary paragraph
- selected_experiences: Array of chosen experiences with tailored descriptions
- highlighted_skills: Array of most relevant skills
- additional_sections: Object with any other relevant sections from the input"""

        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.2,
            }
        )
        
        # Check if response is empty
        if not response or not response.text or response.text.strip() == "":
            logger.error("Empty response received from Gemini API")
            return None
            
        # Clean up response text
        json_str = response.text.strip()
        
        # Add debug logging for the response
        logger.debug(f"API response first 100 chars: {json_str[:100]}...")
        
        # Clean up any markdown code block formatting
        json_str = re.sub(r'^```.*?\n', '', json_str)  # Remove opening ```json
        json_str = re.sub(r'\n```$', '', json_str)     # Remove closing ```
        
        # Try to extract just a JSON object if there's other text
        match = re.search(r'({[\s\S]*})', json_str)
        if match:
            json_str = match.group(1)
            
        try:
            content = json.loads(json_str)
            
            # Add any custom sections from the database
            content['additional_sections'] = {
                name: text for name, text in sections.items()
                if name.lower() not in ['summary', 'experience', 'skills', 'contact information']
            }
            
            return content
            
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing error: {str(je)}")
            logger.debug(f"Invalid JSON content: {json_str}")
            return None
        
    except Exception as e:
        logger.error(f"Error generating tailored resume: {str(e)}")
        return None

def generate_cover_letter(job_info, resume_content, skills):
    """Generate cover letter content matching the resume"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""You are an expert cover letter writer. Create a compelling cover letter that complements this resume and targets the specific job.

Job Information:
{json.dumps(job_info, indent=2)}

Resume Content:
{json.dumps(resume_content, indent=2)}

Skills:
{json.dumps(skills, indent=2)}

Instructions:
1. Create a professional greeting
2. Write an engaging opening paragraph
3. Develop 2-3 body paragraphs highlighting relevant experience
4. Include a strong closing paragraph
5. Add a professional signature block

Return a JSON object with:
- greeting: Professional salutation
- opening: Introduction paragraph
- body_paragraphs: Array of body paragraphs
- closing: Closing paragraph
- signature: Signature block"""

        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1500,
                "temperature": 0.3,
            }
        )
        
        # Check if response is empty
        if not response or not response.text or response.text.strip() == "":
            logger.error("Empty response received from Gemini API for cover letter")
            return None
            
        # Clean up response text
        json_str = response.text.strip()
        
        # Add debug logging for the response
        logger.debug(f"Cover letter API response first 100 chars: {json_str[:100]}...")
        
        # Clean up any markdown code block formatting
        json_str = re.sub(r'^```.*?\n', '', json_str)  # Remove opening ```json
        json_str = re.sub(r'\n```$', '', json_str)     # Remove closing ```
        
        # Try to extract just a JSON object if there's other text
        match = re.search(r'({[\s\S]*})', json_str)
        if match:
            json_str = match.group(1)
            
        try:
            content = json.loads(json_str)
            return content
            
        except json.JSONDecodeError as je:
            logger.error(f"Cover letter JSON parsing error: {str(je)}")
            logger.debug(f"Invalid cover letter JSON content: {json_str}")
            return None
        
    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
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
        
        # First pass: Generate structured content with Gemini
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
        cover_letter_content = generate_cover_letter(job_info, resume_content, skills)
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
        
        # Create job directory and save documents
        job_dir = create_job_directory(job_info)
        
        # Save text versions
        resume_txt_path = job_dir / "resume.txt"
        cover_letter_txt_path = job_dir / "cover_letter.txt"
        
        # Create README.md instead of job_details.json
        readme_path = job_dir / "README.md"
        
        with open(resume_txt_path, 'w') as f:
            f.write(resume_text)
        
        with open(cover_letter_txt_path, 'w') as f:
            f.write(cover_letter_text)
        
        # Generate PDF versions
        ats_resume_pdf_path = job_dir / "resume_ats.pdf"  # ATS-friendly version
        visual_resume_pdf_path = job_dir / "resume_visual.pdf" if use_visual_resume else None
        default_resume_pdf_path = job_dir / "resume.pdf"  # The main resume file
        cover_letter_pdf_path = job_dir / "cover_letter.pdf"
        
        if setup_pdf_environment():
            try:
                # Create ATS-friendly resume (simple format for parsing)
                create_resume_pdf(resume_content, str(ats_resume_pdf_path.with_suffix('')))
                
                # Create visual resume if requested
                if use_visual_resume:
                    from pdf_generator import create_visual_resume_pdf
                    create_visual_resume_pdf(resume_content, str(visual_resume_pdf_path.with_suffix('')))
                    
                # Create default resume (copy of visual resume if enabled, otherwise ATS version)
                if use_visual_resume and visual_resume_pdf_path.exists():
                    import shutil
                    shutil.copy(visual_resume_pdf_path, default_resume_pdf_path)
                else:
                    import shutil
                    shutil.copy(ats_resume_pdf_path, default_resume_pdf_path)
                
                # Create cover letter
                create_cover_letter_pdf(cover_letter_content, job_info, str(cover_letter_pdf_path.with_suffix('')))
                logger.info("Successfully generated PDF documents")
            except Exception as e:
                logger.error(f"Error generating PDF documents: {str(e)}")
                default_resume_pdf_path = resume_txt_path
                cover_letter_pdf_path = resume_txt_path
        else:
            logger.warning("PDF environment not available, using text versions only")
            default_resume_pdf_path = resume_txt_path
            cover_letter_pdf_path = cover_letter_txt_path
        
        # Generate README.md with markdown content instead of job_details.json
        markdown_content = generate_readme_markdown(job_info)
        with open(readme_path, 'w') as f:
            f.write(markdown_content)
            
        # Track job application in the database - use default resume as the main resume
        job_id, application_id = track_job_application(job_info, str(default_resume_pdf_path), str(cover_letter_pdf_path))
        
        logger.info(f"Successfully generated documents in {job_dir}")
        
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
        
        # Return paths to the main resume and cover letter
        return str(default_resume_pdf_path), str(cover_letter_pdf_path)
        
    except Exception as e:
        logger.error(f"Error generating job documents: {str(e)}")
        return None, None

def main():
    """Main entry point for document generation"""
    import argparse
    parser = argparse.ArgumentParser(description='Generate tailored resume and cover letter')
    parser.add_argument('job_info_path', help='Path to job details JSON file')
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
        # Load job info from file
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
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())