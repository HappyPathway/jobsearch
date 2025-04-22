#!/usr/bin/env python3
from pathlib import Path
import shutil
import json
import re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from logging_utils import setup_logging
from models import Experience, Skill, ResumeSection, TargetRole, get_session
import google.generativeai as genai
from dotenv import load_dotenv
import os
import tempfile
from gcs_utils import gcs
from structured_prompt import StructuredPrompt

logger = setup_logging('github_pages')
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generate_tagline(experiences, skills, target_roles):
    """Generate a professional tagline using Gemini"""
    try:
        # Initialize StructuredPrompt
        structured_prompt = StructuredPrompt()

        # Prepare context for Gemini
        recent_exp = experiences[0] if experiences else None
        top_skills = [skill.skill_name for skill in skills[:5]]
        top_role = target_roles[0] if target_roles else None

        # Define expected structure
        expected_structure = {
            "tagline": str
        }

        # Example data
        example_data = {
            "tagline": "Senior Cloud Architect Specializing in Enterprise Digital Transformation"
        }

        # Get structured response
        response = structured_prompt.get_structured_response(
            prompt=f"""Create a short, impactful professional tagline (one line, no more than 10 words).
Focus on my core expertise and career level.

Current Role: {recent_exp.title if recent_exp else ""}
Top Skills: {', '.join(top_skills)}
Target Role: {top_role.role_name if top_role else ""}

The tagline should:
1. Be concise and memorable
2. Reflect senior/principal level
3. Emphasize technical leadership
4. Avoid buzzwords
5. Sound natural, not marketing-speak""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if response:
            tagline = response.get('tagline', '').strip().strip('"').strip("'")
            return tagline

        logger.error("Failed to generate tagline")
        return "Senior Technology Leader & Cloud Architecture Expert"

    except Exception as e:
        logger.error(f"Error generating tagline: {str(e)}")
        return "Senior Technology Leader & Cloud Architecture Expert"

def generate_professional_summary(experiences, skills, target_roles):
    """Generate a professional summary using Gemini"""
    try:
        # Initialize StructuredPrompt
        structured_prompt = StructuredPrompt()

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

        # Define expected structure
        expected_structure = {
            "headline": str,
            "summary": [str],
            "key_points": [str],
            "target_roles": [str]
        }

        # Example data
        example_data = {
            "headline": "Results-driven technology leader with 15+ years of cloud and infrastructure expertise",
            "summary": [
                "Experienced architect specializing in cloud transformation and DevOps practices",
                "Proven track record of leading complex technical initiatives and high-performing teams",
                "Passionate about implementing innovative solutions that drive business value"
            ],
            "key_points": [
                "Led enterprise-wide cloud migration initiatives",
                "Implemented modern DevOps practices and tooling",
                "Reduced infrastructure costs by 40%"
            ],
            "target_roles": [
                "Senior Cloud Architect",
                "Platform Engineering Leader",
                "DevOps Director"
            ]
        }

        # Get structured response
        response = structured_prompt.get_structured_response(
            prompt=f"""Create a structured professional summary that showcases expertise and career goals.

Experience:
{exp_context}

Key Skills:
{top_skills}

Target Roles:
{roles_context}

Create a compelling summary that:
1. Opens with an attention-grabbing headline
2. Provides 2-3 paragraphs of career narrative
3. Highlights key achievements and impact
4. Aligns with target roles
5. Uses strong, active language
6. Maintains professional tone""",
            expected_structure=expected_structure,
            example_data=example_data
        )

        if response:
            # Format the summary sections
            formatted_summary = "\n\n".join([
                response['headline'],
                *response['summary'],
                "\nKey Points:",
                *[f"• {point}" for point in response['key_points']],
                "\nTarget Roles:",
                *[f"• {role}" for role in response['target_roles']]
            ])
            return formatted_summary

        logger.error("Failed to generate professional summary")
        return ""

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