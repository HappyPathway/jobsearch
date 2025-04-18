#!/usr/bin/env python3
from pathlib import Path
import shutil
import json
from jinja2 import Environment, FileSystemLoader
from utils import setup_logging, session_scope
from models import Experience, Skill, ResumeSection, TargetRole

logger = setup_logging('github_pages')

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
        
        with session_scope() as session:
            # Get all required data from database
            experiences = session.query(Experience).order_by(
                Experience.end_date.desc(),
                Experience.start_date.desc()
            ).all()
            
            skills = session.query(Skill).all()
            
            summary = session.query(ResumeSection).filter_by(
                section_name='summary'
            ).first()
            
            target_roles = session.query(TargetRole).order_by(
                TargetRole.priority
            ).limit(5).all()
            
            # Prepare data for template
            template_data = {
                'name': profile['contact_info']['name'],
                'summary': summary.content if summary else '',
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
                'skills': [
                    {
                        'name': skill.skill_name,
                        'count': len(skill.experiences)
                    }
                    for skill in skills
                ],
                'target_roles': [
                    {
                        'name': role.role_name,
                        'match_score': role.match_score,
                        'reasoning': role.reasoning
                    }
                    for role in target_roles
                ],
                'profile': profile  # Pass the entire profile to the template for additional data if needed
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