import sqlite3
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re
from datetime import datetime
from utils import setup_logging
import shutil
from slugify import slugify
from pdf_generator import create_resume_pdf, create_cover_letter_pdf, setup_pdf_environment

logger = setup_logging('generate_documents')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_profile_data():
    """Get all profile data from database"""
    conn = sqlite3.connect('career_data.db')
    c = conn.cursor()
    
    # Get experiences
    c.execute("""
        SELECT company, title, start_date, end_date, description
        FROM experiences
        ORDER BY 
            CASE WHEN end_date = 'Present' THEN '9999-12'
                 ELSE end_date 
            END DESC,
            start_date DESC
    """)
    experiences = [
        {
            "company": row[0],
            "title": row[1],
            "start_date": row[2],
            "end_date": row[3],
            "description": row[4]
        }
        for row in c.fetchall()
    ]
    
    # Get skills
    c.execute("SELECT skill_name FROM skills")
    skills = [row[0] for row in c.fetchall()]
    
    # Get resume sections including contact info
    c.execute("SELECT section_name, content FROM resume_sections")
    sections = {row[0]: row[1] for row in c.fetchall()}
    
    # Get name from contact info section
    c.execute("SELECT content FROM resume_sections WHERE section_name = 'Contact Information'")
    contact_info = c.fetchone()
    full_name = ''
    if contact_info:
        # Try to extract name from contact info
        contact_lines = contact_info[0].split('\n')
        if contact_lines:
            full_name = contact_lines[0].strip()  # Usually name is the first line
    
    conn.close()
    return experiences, skills, sections, full_name

def generate_tailored_resume(job_info, experiences, skills, sections):
    """Generate a resume tailored to a specific job"""
    logger.info(f"Generating tailored resume for {job_info['title']} at {job_info['company']}")
    
    prompt = f"""You are an expert resume writer. Create a tailored resume for this specific job opportunity.
Return ONLY a valid JSON object with no additional text, markdown formatting, or code block markers.

Job Details:
Title: {job_info['title']}
Company: {job_info['company']}
Description: {job_info['description']}
Key Requirements: {', '.join(job_info.get('key_requirements', []))}

Candidate's Experiences:
{json.dumps(experiences, indent=2)}

Skills:
{', '.join(skills)}

Additional Sections:
{json.dumps(sections, indent=2)}

Required JSON format (replace with actual values, keep structure exactly as shown):
{{
    "summary": "2-3 sentences highlighting most relevant experience and skills for this role",
    "selected_experiences": [
        {{
            "company": "company name",
            "title": "job title",
            "dates": "date range",
            "description": "tailored bullet points emphasizing relevant achievements",
            "relevance_score": 85
        }}
    ],
    "highlighted_skills": [
        "skill1",
        "skill2"
    ],
    "additional_sections": {{
        "section_name": "content"
    }}
}}"""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.2,
            }
        )
        
        # Clean up the response
        json_str = response.text.strip()
        json_str = re.sub(r'^```.*?\n', '', json_str)  # Remove opening ```json
        json_str = re.sub(r'\n```$', '', json_str)     # Remove closing ```
        
        # Try to extract just the JSON object if there's other text
        match = re.search(r'({[\s\S]*})', json_str)
        if match:
            json_str = match.group(1)
        
        try:
            resume_content = json.loads(json_str)
            
            # Validate and normalize the content
            required_fields = {
                'summary': '',
                'selected_experiences': [],
                'highlighted_skills': [],
                'additional_sections': {}
            }
            
            # Ensure all required fields exist
            for field, default in required_fields.items():
                if field not in resume_content:
                    resume_content[field] = default
            
            # Validate experiences
            if not isinstance(resume_content['selected_experiences'], list):
                resume_content['selected_experiences'] = []
            
            for exp in resume_content['selected_experiences']:
                if not isinstance(exp, dict):
                    continue
                # Ensure all required fields exist in experience
                exp_fields = {
                    'company': '',
                    'title': '',
                    'dates': '',
                    'description': '',
                    'relevance_score': 0
                }
                for field, default in exp_fields.items():
                    if field not in exp:
                        exp[field] = default
                
                # Normalize relevance score
                try:
                    exp['relevance_score'] = max(0, min(100, float(exp['relevance_score'])))
                except (ValueError, TypeError):
                    exp['relevance_score'] = 0
            
            # Validate skills
            if not isinstance(resume_content['highlighted_skills'], list):
                resume_content['highlighted_skills'] = []
            
            # Validate additional sections
            if not isinstance(resume_content['additional_sections'], dict):
                resume_content['additional_sections'] = {}
            
            logger.info("Successfully generated tailored resume content")
            return resume_content
            
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing error: {str(je)}")
            logger.debug(f"Problematic JSON string: {json_str}")
            return None
            
    except Exception as e:
        logger.error(f"Error generating resume: {str(e)}")
        return None

def generate_cover_letter(job_info, resume_content, skills):
    """Generate a cover letter tailored to a specific job"""
    logger.info(f"Generating cover letter for {job_info['title']} at {job_info['company']}")
    
    prompt = f"""You are an expert cover letter writer. Create a compelling cover letter for this specific job opportunity.
Return ONLY a valid JSON object with no additional text, markdown formatting, or code block markers.

Job Details:
Title: {job_info['title']}
Company: {job_info['company']}
Description: {job_info['description']}
Key Requirements: {', '.join(job_info.get('key_requirements', []))}

Tailored Resume Summary:
{resume_content['summary']}

Top Relevant Experiences:
{json.dumps(resume_content['selected_experiences'][:2], indent=2)}

Key Skills for Role:
{', '.join(resume_content['highlighted_skills'][:5])}

Required JSON format (replace with actual values, keep structure exactly as shown):
{{
    "greeting": "Dear Hiring Manager,",
    "opening": "engaging opening paragraph",
    "body_paragraphs": [
        "paragraph showing role fit",
        "paragraph highlighting achievements",
        "paragraph showing culture fit"
    ],
    "closing": "strong closing with call to action",
    "signature": "Sincerely,\\nYour Name"
}}"""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1500,
                "temperature": 0.3,
            }
        )
        
        # Clean up the response
        json_str = response.text.strip()
        json_str = re.sub(r'^```.*?\n', '', json_str)  # Remove opening ```json
        json_str = re.sub(r'\n```$', '', json_str)     # Remove closing ```
        
        # Try to extract just the JSON object if there's other text
        match = re.search(r'({[\s\S]*})', json_str)
        if match:
            json_str = match.group(1)
        
        try:
            cover_letter_content = json.loads(json_str)
            
            # Validate and normalize the content
            required_fields = {
                'greeting': 'Dear Hiring Manager,',
                'opening': '',
                'body_paragraphs': [],
                'closing': '',
                'signature': 'Sincerely,'
            }
            
            # Ensure all required fields exist
            for field, default in required_fields.items():
                if field not in cover_letter_content:
                    cover_letter_content[field] = default
            
            # Validate body paragraphs
            if not isinstance(cover_letter_content['body_paragraphs'], list):
                cover_letter_content['body_paragraphs'] = []
            
            # Ensure we have at least one body paragraph
            if not cover_letter_content['body_paragraphs']:
                cover_letter_content['body_paragraphs'] = ['']
            
            logger.info("Successfully generated cover letter content")
            return cover_letter_content
            
        except json.JSONDecodeError as je:
            logger.error(f"JSON parsing error: {str(je)}")
            logger.debug(f"Problematic JSON string: {json_str}")
            return None
            
    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
        return None

def format_resume(content):
    """Format resume content into a presentable text document"""
    output = []
    
    # Header section (could be customized with contact info)
    output.append("PROFESSIONAL RESUME")
    output.append("=" * 80 + "\n")
    
    # Summary
    output.append("PROFESSIONAL SUMMARY")
    output.append("-" * 80)
    output.append(content['summary'])
    output.append("")
    
    # Experience
    output.append("PROFESSIONAL EXPERIENCE")
    output.append("-" * 80)
    for exp in sorted(content['selected_experiences'], 
                     key=lambda x: x['relevance_score'], reverse=True):
        if not isinstance(exp, dict):
            continue
        output.append(f"{exp.get('title', '')} - {exp.get('company', '')}")
        output.append(f"{exp.get('dates', '')}")
        output.append(str(exp.get('description', '')))
        output.append("")
    
    # Skills
    output.append("TECHNICAL SKILLS")
    output.append("-" * 80)
    # Convert complex types to strings and join
    skills = []
    for skill in content.get('highlighted_skills', []):
        if isinstance(skill, (list, dict)):
            skills.extend(str(s).strip() for s in skill)
        else:
            skills.append(str(skill).strip())
    output.append(", ".join(skills))
    output.append("")
    
    # Additional sections
    for section, content in content.get('additional_sections', {}).items():
        if not isinstance(content, str):
            content = str(content)
        output.append(section.upper())
        output.append("-" * 80)
        output.append(content)
        output.append("")
    
    return "\n".join(output)

def write_cover_letter_with_gemini(cover_letter_content, job_info):
    """Use Gemini with a specialized writing prompt to create an engaging cover letter"""
    try:
        prompt = f"""You are an expert cover letter writer known for creating compelling, personalized letters that demonstrate genuine interest and fit.
Transform this structured content into an engaging cover letter that shows enthusiasm, relevance, and personality.

IMPORTANT: Do not include any placeholders, template text, or [brackets] in your response. 
Instead of using placeholders, write actual content based on the company and role information provided.
Never include 'Your Name' at the end - the system will handle the signature.

Job Details:
{json.dumps(job_info, indent=2)}

Content to transform:
{json.dumps(cover_letter_content, indent=2)}

Guidelines:
- Open with a strong hook that shows genuine interest in their specific mission
- Connect your experience directly to the company's needs
- Tell a compelling story about your relevant achievements
- Show enthusiasm without being generic
- Demonstrate cultural fit
- Close with confidence and clear next steps
- DO NOT use any placeholders or template text
- DO NOT include [bracketed text]
- Write specific, concrete details about the company and role

Keep the tone professional but personable. Make the reader feel this letter was written specifically for their company and role."""

        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1500,
                "temperature": 0.7,
            }
        )
        
        formatted_letter = response.text.strip()
        
        # Validate no placeholders exist
        placeholder_patterns = [
            r'\[.*?\]',  # Matches anything in square brackets
            r'<.*?>',    # Matches anything in angle brackets
            r'\{.*?\}',  # Matches anything in curly braces
            r'Your Name',
            r'\[NAME\]',
            r'\(.*?\)',  # Matches anything in parentheses that looks like a placeholder
            r'COMPANY NAME',
            r'JOB TITLE',
            r'INSERT.*?HERE',
            r'PLACEHOLDER',
        ]
        
        for pattern in placeholder_patterns:
            if re.search(pattern, formatted_letter, re.IGNORECASE):
                logger.warning(f"Found potential placeholder matching pattern {pattern}. Regenerating letter.")
                return write_cover_letter_with_gemini(cover_letter_content, job_info)  # Retry generation
        
        logger.info("Successfully generated engaging cover letter content with no placeholders")
        return formatted_letter
        
    except Exception as e:
        logger.error(f"Error generating engaging cover letter content: {str(e)}")
        return None
    output.append("Re: Application for " + job_info['title'])
    output.append("")
    
    # Letter content
    output.append(content['greeting'])
    output.append("")
    
    output.append(content['opening'])
    output.append("")
    
    # Ensure body paragraphs are strings and don't contain placeholders
    for paragraph in content['body_paragraphs']:
        if isinstance(paragraph, (list, dict)):
            paragraph = str(paragraph)
        output.append(paragraph)
        output.append("")
    
    output.append(content['closing'])
    output.append("")
    output.append("Sincerely,")  # Fixed signature instead of using a placeholder
    output.append("Daniel Arnold")  # Use actual name instead of placeholder
    
    return "\n".join(output)

def create_job_directory(job_info):
    """Create a directory for the job application"""
    logger.info(f"Creating directory for {job_info['title']} at {job_info['company']}")
    
    # Create a slug from company and title for the directory name
    company_slug = slugify(job_info['company'])
    title_slug = slugify(job_info['title'])
    date_str = datetime.now().strftime("%Y-%m-%d")
    dir_name = f"{date_str}_{company_slug}_{title_slug}"
    
    # Create the applications directory if it doesn't exist
    applications_dir = Path(__file__).parent.parent / 'applications'
    applications_dir.mkdir(exist_ok=True)
    
    # Create job-specific directory
    job_dir = applications_dir / dir_name
    job_dir.mkdir(exist_ok=True)
    
    return job_dir

def write_resume_with_gemini(resume_content):
    """Use Gemini with a specialized writing prompt to create engaging resume content"""
    try:
        prompt = f"""You are an expert resume writer known for creating compelling, engaging resumes that catch recruiters' attention.
Take this structured content and transform it into powerful, achievement-focused prose that will make the candidate stand out.
Focus on strong action verbs, quantifiable achievements, and clear impact. Make every word count.

Content to transform:
{json.dumps(resume_content, indent=2)}

Guidelines:
- Start each bullet point with powerful action verbs
- Include metrics and specific achievements wherever possible
- Focus on impact and results, not just responsibilities
- Use industry-relevant keywords naturally
- Keep language professional but engaging
- Highlight growth and progression
- Make achievements concrete and specific

Format the resume professionally with clear sections for:
1. Professional Summary (compelling 2-3 sentence hook)
2. Professional Experience (achievement-focused bullet points)
3. Technical Skills (organized and prioritized)
4. Additional sections as provided

Return the text in a clear, organized format ready for the PDF template."""

        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.7,
            }
        )
        
        formatted_resume = response.text.strip()
        logger.info("Successfully generated engaging resume content")
        return formatted_resume
        
    except Exception as e:
        logger.error(f"Error generating engaging resume content: {str(e)}")
        return None

def generate_job_documents(job_info, use_writing_pass=True):
    """Generate both resume and cover letter for a specific job"""
    logger.info(f"Generating documents for {job_info['title']} at {job_info['company']}")
    
    try:
        # Get profile data
        experiences, skills, sections = get_profile_data()
        
        # First pass: Generate structured content with Gemini
        resume_content = generate_tailored_resume(job_info, experiences, skills, sections)
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
        job_info_path = job_dir / "job_details.json"
        
        with open(resume_txt_path, 'w') as f:
            f.write(resume_text)
        
        with open(cover_letter_txt_path, 'w') as f:
            f.write(cover_letter_text)
        
        # Generate PDF versions
        resume_pdf_path = job_dir / "resume.pdf"
        cover_letter_pdf_path = job_dir / "cover_letter.pdf"
        
        if setup_pdf_environment():
            try:
                create_resume_pdf(resume_content, str(resume_pdf_path.with_suffix('')))
                create_cover_letter_pdf(cover_letter_content, job_info, str(cover_letter_pdf_path.with_suffix('')))
                logger.info("Successfully generated PDF documents")
            except Exception as e:
                logger.error(f"Error generating PDF documents: {str(e)}")
                resume_pdf_path = resume_txt_path
                cover_letter_pdf_path = cover_letter_txt_path
        else:
            logger.warning("PDF environment not available, using text versions only")
            resume_pdf_path = resume_txt_path
            cover_letter_pdf_path = cover_letter_txt_path
            
        # Save job details for reference
        with open(job_info_path, 'w') as f:
            json.dump({
                'title': job_info['title'],
                'company': job_info['company'],
                'url': job_info.get('url', ''),
                'description': job_info.get('description', ''),
                'match_score': job_info.get('match_score', 0),
                'application_priority': job_info.get('application_priority', 'low'),
                'key_requirements': job_info.get('key_requirements', []),
                'culture_indicators': job_info.get('culture_indicators', []),
                'career_growth_potential': job_info.get('career_growth_potential', ''),
                'generated_date': datetime.now().isoformat()
            }, f, indent=2)
        
        logger.info(f"Successfully generated documents in {job_dir}")
        return str(resume_pdf_path), str(cover_letter_pdf_path)
        
    except Exception as e:
        logger.error(f"Error generating job documents: {str(e)}")
        return None, None

if __name__ == "__main__":
    # Example usage
    job_info = {
        "title": "Senior Cloud Architect",
        "company": "Example Corp",
        "description": "Looking for an experienced cloud architect...",
        "key_requirements": ["AWS", "Terraform", "Kubernetes"]
    }
    generate_job_documents(job_info)