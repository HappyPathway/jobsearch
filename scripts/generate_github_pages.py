#!/usr/bin/env python3
import json
import shutil
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from utils import setup_logging

logger = setup_logging('github_pages')

def copy_profile_image(docs_dir, output_dir):
    """Copy profile image to assets directory"""
    profile_img = docs_dir / 'Profile.jpeg'
    if profile_img.exists():
        assets_dir = output_dir / 'assets'
        assets_dir.mkdir(exist_ok=True)
        shutil.copy(profile_img, assets_dir / 'profile.jpg')
        return 'assets/profile.jpg'
    return ''

def generate_site():
    """Generate GitHub Pages site from profile data"""
    script_dir = Path(__file__).parent
    workspace_dir = script_dir.parent
    docs_dir = workspace_dir / 'docs'
    
    # Create pages directory if it doesn't exist
    pages_dir = workspace_dir / 'pages'
    pages_dir.mkdir(exist_ok=True)
    
    # Load profile data
    with open(docs_dir / 'profile.json') as f:
        profile = json.load(f)
    
    # Copy and get profile image path
    profile_img_path = copy_profile_image(docs_dir, pages_dir)
    
    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader(script_dir / 'templates'))
    template = env.get_template('github_pages.html')
    
    # Render the template with our data
    html = template.render(
        profile=profile,
        profile_image=profile_img_path,
        last_updated=datetime.now().strftime('%B %d, %Y')
    )
    
    # Write the generated HTML
    with open(pages_dir / 'index.html', 'w') as f:
        f.write(html)
    
    logger.info('Successfully generated GitHub Pages site in pages directory')

if __name__ == '__main__':
    generate_site()