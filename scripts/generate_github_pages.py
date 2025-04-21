#!/usr/bin/env python3
from pathlib import Path
import shutil
import json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from logging_utils import setup_logging
from models import Experience, Skill, ResumeSection, TargetRole, get_session
import google.generativeai as genai
from dotenv import load_dotenv
import os
import tempfile
from gcs_utils import gcs

logger = setup_logging('github_pages')
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generate_tagline(experiences, skills, target_roles):
    """Generate a professional tagline using Gemini"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Prepare context for Gemini
        recent_exp = experiences[0] if experiences else None
        top_skills = [skill.skill_name for skill in skills[:5]]
        top_role = target_roles[0] if target_roles else None
        
        prompt = f"""Create a short, impactful professional tagline (one line, no more than 10 words).
Focus on my core expertise and career level.

Current Role: {recent_exp.title if recent_exp else ""}
Top Skills: {', '.join(top_skills)}
Target Role: {top_role.role_name if top_role else ""}

The tagline should:
1. Be concise and memorable
2. Reflect senior/principal level
3. Emphasize technical leadership
4. Avoid buzzwords
5. Sound natural, not marketing-speak"""

        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 50,
                "temperature": 0.2,
            }
        )
        
        # Clean up response - remove quotes if present
        tagline = response.text.strip().strip('"').strip("'")
        return tagline
        
    except Exception as e:
        logger.error(f"Error generating tagline: {str(e)}")
        return "Senior Technology Leader & Cloud Architecture Expert"

def generate_professional_summary(experiences, skills, target_roles):
    """Generate a professional summary using Gemini"""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Prepare context for Gemini
        exp_context = "\n".join([
            f"- {exp.title} at {exp.company} ({exp.start_date} - {exp.end_date}): {exp.description}"
            for exp in experiences[:3]  # Most recent 3 experiences
        ])
        
        top_skills = ", ".join([skill.skill_name for skill in skills[:10]])
        
        roles_context = "\n".join([
            f"- {role.role_name} (Match Score: {role.match_score}): {role.reasoning}"
            for role in target_roles[:3]
        ])
        
        prompt = f"""As an expert career advisor, create a concise 2-3 paragraph professional summary.
Focus on high-level career narrative, key strengths, and target roles.
Write in first person. Be specific but concise.

Recent Experience:
{exp_context}

Key Skills:
{top_skills}

Target Roles:
{roles_context}

Write a compelling summary that:
1. Highlights my expertise and impact
2. Shows progression and growth
3. Indicates what roles I'm targeting
4. Emphasizes unique value proposition"""

        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 500,
                "temperature": 0.2,
            }
        )
        
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Error generating professional summary: {str(e)}")
        return ""

def generate_pages():
    """Generate static GitHub Pages and store in GCS"""
    try:
        # Create temporary directory for generation
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # Get profile data from database
            with get_session() as session:
                experiences = session.query(Experience).order_by(Experience.end_date.desc()).all()
                skills = session.query(Skill).all()
                target_roles = session.query(TargetRole).order_by(TargetRole.match_score.desc()).all()
                sections = dict(
                    session.query(ResumeSection.section_name, ResumeSection.content)
                    .all()
                )
            
            # Generate profile/tagline
            tagline = generate_tagline(experiences, skills, target_roles)
            professional_summary = generate_professional_summary(experiences, skills, target_roles)
            
            # Prepare profile data
            profile = {
                'tagline': tagline,
                'summary': professional_summary,
                'sections': sections
            }
            
            # Load and render template
            env = Environment(loader=FileSystemLoader(Path(__file__).parent))
            template = env.get_template('templates/github_pages.html')
            
            # Prepare template data
            template_data = {
                'profile': profile,
                'current_date': datetime.now().strftime('%B %d, %Y'),
                'profile_image': 'assets/profile.jpg'
            }
            
            # Generate HTML
            html = template.render(**template_data)
            
            # Write HTML file to temp directory
            temp_index = temp_dir_path / 'index.html'
            temp_index.write_text(html)

            # Store in GCS under pages/
            gcs.upload_file(temp_index, 'pages/index.html')
            
            # Copy static assets to GCS if they exist
            static_src = Path(__file__).parent / 'static'
            if static_src.exists():
                for file in static_src.rglob('*'):
                    if file.is_file():
                        rel_path = file.relative_to(static_src)
                        gcs_path = f'pages/static/{rel_path}'
                        gcs.upload_file(file, gcs_path)
            
            # Copy profile picture from /docs directory to GCS pages/assets
            profile_src = Path(__file__).parent.parent / 'inputs' / 'Profile.jpeg'
            if profile_src.exists():
                gcs.upload_file(profile_src, 'pages/assets/profile.jpg')
            
            logger.info("Successfully generated GitHub Pages and stored in GCS")
            return True
            
    except Exception as e:
        logger.error(f"Error generating GitHub Pages: {str(e)}")
        return False

def main():
    """Main entry point"""
    if generate_pages():
        print("Successfully generated GitHub Pages")
    else:
        print("Failed to generate GitHub Pages")
        exit(1)

if __name__ == "__main__":
    main()