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
    """Generate static GitHub Pages from career data"""
    logger.info("Starting GitHub Pages generation")
    
    # Set up Jinja2 environment
    env = Environment(
        loader=FileSystemLoader('scripts/templates'),
        trim_blocks=True,
        lstrip_blocks=True
    )
    template = env.get_template('github_pages.html')
    
    try:
        # Load profile data from profile.json
        profile_json_path = Path(__file__).parent.parent / 'docs' / 'profile.json'
        with open(profile_json_path, 'r') as f:
            profile = json.load(f)
        
        if not profile:
            logger.error("Profile data is empty or not loaded properly")
            return False
        
        with get_session() as session:
            # Get all required data from database
            experiences = session.query(Experience).order_by(
                Experience.end_date.desc(),
                Experience.start_date.desc()
            ).all()
            
            db_skills = session.query(Skill).all()
            
            summary = session.query(ResumeSection).filter_by(
                section_name='summary'
            ).first()
            
            target_roles = session.query(TargetRole).order_by(
                TargetRole.priority
            ).limit(5).all()
            
            # Generate professional tagline and summary
            tagline = generate_tagline(experiences, db_skills, target_roles)
            professional_summary = generate_professional_summary(experiences, db_skills, target_roles)
            
            # Create a mapping of skill names to their usage count from the database
            skill_usage_counts = {
                skill.skill_name: len(skill.experiences)
                for skill in db_skills
            }
            
            # Combine skills from profile.json with database usage counts
            combined_skills = {}
            
            # Add skills from profile.json core_skills categories
            for category, skills in profile.get('core_skills', {}).items():
                for skill in skills:
                    skill_name = skill.get('name')
                    if skill_name:
                        combined_skills[skill_name] = {
                            'name': skill_name,
                            'proficiency': skill.get('proficiency', 'intermediate'),
                            'years': skill.get('years', 1),
                            'last_used': skill.get('last_used', '2024'),
                            'context': skill.get('context', ''),
                            'count': skill_usage_counts.get(skill_name, 0),
                            'category': category.replace('_', ' ').title()
                        }
            
            # Add any remaining skills from database that weren't in profile.json
            for skill in db_skills:
                if skill.skill_name not in combined_skills:
                    combined_skills[skill.skill_name] = {
                        'name': skill.skill_name,
                        'proficiency': 'intermediate',
                        'years': 1,
                        'last_used': '2024',
                        'context': '',
                        'count': len(skill.experiences),
                        'category': 'Additional Skills'
                    }
            
            # Group skills by category
            categorized_skills = {}
            for skill in combined_skills.values():
                category = skill['category']
                if category not in categorized_skills:
                    categorized_skills[category] = []
                categorized_skills[category].append(skill)
            
            # Sort skills within each category by proficiency and usage count
            proficiency_scores = {'expert': 3, 'advanced': 2, 'intermediate': 1}
            for category in categorized_skills:
                categorized_skills[category].sort(
                    key=lambda x: (
                        proficiency_scores.get(x['proficiency'], 0),
                        x['count'],
                        x['years']
                    ),
                    reverse=True
                )
            
            # Prepare data for template
            template_data = {
                'name': profile['contact_info']['name'],
                'tagline': tagline,
                'summary': summary.content if summary else '',
                'professional_summary': professional_summary,
                'experiences': [
                    {
                        'company': exp.company,
                        'title': exp.title,
                        'start_date': exp.start_date,
                        'end_date': exp.end_date,
                        'description': exp.description,
                        'skills': [s.skill_name for s in exp.skills]
                    }
                    for exp in experiences
                ],
                'categorized_skills': categorized_skills,
                'target_roles': [
                    {
                        'name': role.role_name,
                        'match_score': role.match_score,
                        'reasoning': role.reasoning
                    }
                    for role in target_roles
                ],
                'profile': profile,
                'current_date': datetime.now().strftime('%B %d, %Y'),
                'profile_image': 'assets/profile.jpg'
            }
            
            # Generate HTML
            html = template.render(**template_data)
            
            # Ensure pages directory exists
            pages_dir = Path(__file__).parent.parent / 'pages'
            pages_dir.mkdir(exist_ok=True)
            
            # Write HTML file
            index_path = pages_dir / 'index.html'
            with open(index_path, 'w') as f:
                f.write(html)
                
            # Copy static assets
            static_src = Path(__file__).parent / 'static'
            static_dest = pages_dir / 'static'
            if static_src.exists():
                shutil.copytree(static_src, static_dest, dirs_exist_ok=True)
            
            # Copy profile picture if it exists
            profile_src = Path(__file__).parent.parent / 'docs' / 'Profile.jpeg'
            if profile_src.exists():
                profile_dest = pages_dir / 'assets'
                profile_dest.mkdir(exist_ok=True)
                shutil.copy2(profile_src, profile_dest / 'profile.jpg')
            
            logger.info("Successfully generated GitHub Pages")
            return True
            
    except Exception as e:
        logger.error(f"Error generating GitHub Pages: {str(e)}")
        return False

def main():
    if generate_pages():
        print("Successfully generated GitHub Pages")
    else:
        print("Failed to generate GitHub Pages")
        exit(1)

if __name__ == "__main__":
    main()