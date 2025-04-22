#!/usr/bin/env python3
"""
Medium Article Generator and Publisher

This script generates professional articles based on skills identified in job search strategy
and publishes them to Medium using the Medium API.

Usage:
  python medium_publisher.py [--preview] [--skill "Skill Name"]
  
Arguments:
  --preview      Generate article content but don't publish to Medium
  --skill        Specify a particular skill to write about, otherwise uses skills from latest strategy
"""

import os
import sys
import json
import argparse
import random
import time
from datetime import datetime
from pathlib import Path
import logging
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import tempfile

# Add parent directory to Python path to find local modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.logging_utils import setup_logging
from scripts.gcs_utils import GCSUtils
from scripts.structured_prompt import StructuredPrompt

# Set up logging
logger = setup_logging('medium_publisher')

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MEDIUM_API_TOKEN = os.getenv("MEDIUM_API_TOKEN")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

# Configure Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Medium API endpoints
MEDIUM_API_BASE = "https://api.medium.com/v1"
MEDIUM_USER_URL = f"{MEDIUM_API_BASE}/me"
MEDIUM_POST_URL = f"{MEDIUM_API_BASE}/users/{{user_id}}/posts"

class MediumPublisher:
    """Class to generate and publish articles to Medium"""
    def __init__(self, client=None):
        self.client = client or medium.Client()
        self.structured_prompt = StructuredPrompt()
        self.api_token = MEDIUM_API_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.skills_history = {}
        self.user_data = None
        
        # Attempt to authenticate with Medium API
        if self.api_token:
            try:
                self._authenticate()
                logger.info("Successfully authenticated with Medium API")
            except Exception as e:
                logger.error(f"Failed to authenticate with Medium API: {str(e)}")
                self.user_data = None
        else:
            logger.warning("Medium API token not set. Publishing will be disabled.")
    
    def _authenticate(self):
        """Authenticate with Medium API and get user data"""
        response = requests.get(MEDIUM_USER_URL, headers=self.headers)
        if response.status_code == 200:
            self.user_data = response.json().get("data", {})
            logger.info(f"Authenticated as Medium user: {self.user_data.get('name')}")
        else:
            logger.error(f"Authentication failed: {response.text}")
            raise Exception(f"Medium API authentication failed: {response.status_code}")
    
    def _get_latest_strategy_file(self):
        """Get the latest job strategy file"""
        try:
            root_dir = Path(__file__).resolve().parent.parent
            strategy_dir = os.path.join(root_dir, 'strategies')
            
            if not os.path.exists(strategy_dir):
                logger.error(f"Strategy directory not found: {strategy_dir}")
                return None
            
            # Find all strategy files
            strategy_files = [os.path.join(strategy_dir, f) for f in os.listdir(strategy_dir) 
                              if f.startswith('strategy_') and f.endswith('.md')]
            
            if not strategy_files:
                logger.error("No strategy files found")
                return None
            
            # Get the most recent file
            latest_strategy = max(strategy_files, key=os.path.getmtime)
            logger.info(f"Using latest strategy file: {latest_strategy}")
            return latest_strategy
        except Exception as e:
            logger.error(f"Error finding latest strategy file: {str(e)}")
            return None
    
    def _determine_professional_domain(self, skills):
        """Determine the professional domain based on the skills listed in the strategy"""
        try:
            if not GEMINI_API_KEY or not skills:
                logger.warning("Cannot determine professional domain: missing API key or skills")
                return "Professional"
            
            logger.info(f"Determining professional domain from {len(skills)} skills")
            
            # Ask Gemini to analyze the skills and determine the domain
            prompt = f"""Based on the following professional skills, determine the most likely professional domain or industry for this person.
Return only the professional domain or job category as a single word or short phrase (like "Software Engineering" or "Healthcare").

Skills:
{', '.join(skills[:20])}

Some example domains are: Software Engineering, Data Science, Marketing, Finance, Healthcare, Education, Design, etc.
Your response should be a single domain name, no extra text."""
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": 20,
                    "temperature": 0.1,
                }
            )
            
            domain = response.text.strip()
            logger.info(f"Determined professional domain: {domain}")
            return domain
        except Exception as e:
            logger.error(f"Error determining professional domain: {str(e)}")
            return "Professional"
    
    def _extract_skills_from_strategy(self, strategy_file):
        """Extract key skills from the job strategy file"""
        try:
            with open(strategy_file, 'r') as f:
                content = f.read()
            
            skills = []
            
            # Look for skills in the "Key Skills to Emphasize" section
            sections = content.split("#### Key Skills to Emphasize")
            
            for i in range(1, len(sections)):
                section = sections[i].split("####")[0] if "####" in sections[i] else sections[i]
                skill_lines = [line.strip()[2:].strip() for line in section.strip().split("\n") if line.strip().startswith("- ")]
                skills.extend(skill_lines)
            
            # Also look for skills in skill development plan
            if "## Skill Development Plan" in content:
                dev_section = content.split("## Skill Development Plan")[1].split("##")[0]
                skill_headers = [line.strip()[15:].strip() for line in dev_section.split("\n") 
                               if line.strip().startswith("### Current Focus:")]
                skills.extend(skill_headers)
            
            # Remove duplicates while preserving order
            unique_skills = []
            for skill in skills:
                if skill and skill not in unique_skills:
                    unique_skills.append(skill)
            
            return unique_skills
        except Exception as e:
            logger.error(f"Error extracting skills from strategy: {str(e)}")
            return []
    
    def _load_published_history(self):
        """Load history of previously published articles"""
        try:
            # Load publication history from GCS
            gcs_path = 'articles/medium_history.json'
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_path = Path(temp_file.name)
            
            gcs.download_file(gcs_path, temp_path)
            
            with open(temp_path, 'r') as f:
                self.skills_history = json.load(f)
            
            temp_path.unlink()
            
            logger.info(f"Loaded history for {len(self.skills_history)} skills from GCS")
            return self.skills_history
        except Exception as e:
            logger.error(f"Error loading publication history: {str(e)}")
            return {}
    
    def _save_published_history(self):
        """Save history of published articles to GCS"""
        try:
            # Save publication history to GCS
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(self.skills_history, temp_file, indent=2)

            # Upload to GCS
            gcs_path = 'articles/medium_history.json'
            gcs.upload_file(temp_path, gcs_path)

            # Clean up temp file
            temp_path.unlink()
            
            logger.info(f"Saved publication history for {len(self.skills_history)} skills to GCS")
        except Exception as e:
            logger.error(f"Error saving publication history: {str(e)}")
    
    def select_skill_for_article(self, specified_skill=None):
        """Select a skill to write an article about"""
        if specified_skill:
            return specified_skill
        
        # Load history of previously published articles
        self._load_published_history()
        
        # Get the latest strategy file
        strategy_file = self._get_latest_strategy_file()
        if not strategy_file:
            logger.error("No strategy file found, cannot select skill")
            return None
        
        # Extract skills from the strategy file
        skills = self._extract_skills_from_strategy(strategy_file)
        
        if not skills:
            logger.error("No skills found in strategy file")
            return None
        
        logger.info(f"Found {len(skills)} skills in strategy file")
        
        # Prioritize skills that haven't been written about yet
        unpublished_skills = [skill for skill in skills if skill not in self.skills_history]
        
        if unpublished_skills:
            selected_skill = random.choice(unpublished_skills)
            logger.info(f"Selected unpublished skill: {selected_skill}")
        else:
            # Find the skill with the oldest published date
            oldest_skill = min(skills, key=lambda s: self.skills_history.get(s, {}).get('last_published', "2000-01-01"))
            selected_skill = oldest_skill
            logger.info(f"All skills have been published, selected oldest: {selected_skill}")
        
        return selected_skill
    
    def generate_article(self, skill):
        """Generate an article about the specified skill using Gemini"""
        try:
            if not GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY not set")
                return None
            
            logger.info(f"Generating article for skill: {skill}")
            
            # Get the latest strategy file
            strategy_file = self._get_latest_strategy_file()
            if not strategy_file:
                logger.error("No strategy file found, cannot extract skills")
                return None
                
            # Extract all skills from the strategy
            all_skills = self._extract_skills_from_strategy(strategy_file)
            
            # Determine professional domain from the skills
            domain = self._determine_professional_domain(all_skills)
            
            # Define expected structure for outline
            outline_structure = {
                "title": str,
                "subtitle": str,
                "sections": [{
                    "heading": str,
                    "bullet_points": [str]
                }],
                "tags": [str]
            }

            # Example outline data
            example_outline = {
                "title": "Mastering Cloud Architecture: Essential Skills for Modern Tech Leaders",
                "subtitle": "A comprehensive guide to cloud infrastructure design and implementation",
                "sections": [
                    {
                        "heading": "Introduction",
                        "bullet_points": [
                            "The evolution of cloud computing",
                            "Why cloud architecture matters today"
                        ]
                    },
                    {
                        "heading": "Core Concepts",
                        "bullet_points": [
                            "Distributed systems fundamentals",
                            "Scalability patterns and practices"
                        ]
                    }
                ],
                "tags": ["Cloud Computing", "Architecture", "Technology", "Professional Development"]
            }

            # Get structured outline
            outline = self.structured_prompt.get_structured_response(
                prompt=f"""You are an expert writer specializing in {skill} as it relates to the field of {domain}.
Create a detailed outline for a professional blog post about {skill}.

The article should:
1. Show deep expertise (this will be published on Medium to demonstrate professional knowledge)
2. Include practical examples relevant to the {domain} field
3. Be well-structured and comprehensive
4. Target a professional audience

Create an outline with clear sections and key points to cover.""",
                expected_structure=outline_structure,
                example_data=example_outline
            )

            if not outline:
                logger.error("Failed to generate article outline")
                return None

            # Define expected structure for full article
            article_structure = {
                "title": str,
                "subtitle": str,
                "content": str,
                "tags": [str],
                "generated_at": str,
                "skill": str,
                "domain": str
            }

            # Example article data
            example_article = {
                "title": "Mastering Cloud Architecture: Essential Skills for Modern Tech Leaders",
                "subtitle": "A comprehensive guide to cloud infrastructure design and implementation",
                "content": "# Mastering Cloud Architecture\n\nCloud architecture has become...",
                "tags": ["Cloud Computing", "Architecture", "Technology", "Professional Development"],
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "skill": "Cloud Architecture",
                "domain": "Technology"
            }

            # Generate full article based on outline
            article_data = self.structured_prompt.get_structured_response(
                prompt=f"""You are an expert writer specializing in {skill} as it relates to the field of {domain}.
Write a comprehensive, engaging, and well-informed blog post about {skill} using this outline:

{json.dumps(outline, indent=2)}

The article should:
1. Show deep expertise
2. Include practical examples relevant to the {domain} field
3. Use Markdown formatting
4. Have a professional but engaging tone
5. Be well-structured with clear headings (use # for main heading, ## for section headings)
6. Be between 1000-1500 words
7. Include a brief author bio at the end that mentions you're a {domain} professional seeking new opportunities""",
                expected_structure=article_structure,
                example_data=example_article
            )

            if article_data:
                logger.info(f"Generated article: {article_data['title']} ({len(article_data['content'])} chars)")
                return article_data

            logger.error("Failed to generate article content")
            return None

        except Exception as e:
            logger.error(f"Error generating article: {str(e)}")
            return None
    
    def save_article(self, article_data):
        """Save the generated article to GCS"""
        try:
            if not article_data:
                logger.error("No article data to save")
                return None
            
            # Create filename from title and date
            date_str = datetime.now().strftime("%Y-%m-%d")
            title_slug = article_data['title'].lower().replace(" ", "-")
            title_slug = ''.join(c for c in title_slug if c.isalnum() or c == '-')
            
            md_filename = f"{date_str}_{title_slug}.md"
            json_filename = f"{date_str}_{title_slug}.json"
            
            # Store files in GCS
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_md:
                temp_md_path = Path(temp_md.name)
                temp_md.write(article_data['content'])

            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_json:
                temp_json_path = Path(temp_json.name)
                json.dump(article_data, temp_json, indent=2)

            # Upload to GCS
            md_gcs_path = f'articles/{md_filename}'
            json_gcs_path = f'articles/{json_filename}'

            gcs.upload_file(temp_md_path, md_gcs_path)
            gcs.upload_file(temp_json_path, json_gcs_path)

            # Clean up temp files
            temp_md_path.unlink()
            temp_json_path.unlink()
            
            logger.info(f"Article saved to GCS at {md_gcs_path}")
            logger.info(f"Article metadata saved to GCS at {json_gcs_path}")
            
            return md_gcs_path

        except Exception as e:
            logger.error(f"Error saving article: {str(e)}")
            return None
    
    def publish_to_medium(self, article_data):
        """Publish the article to Medium"""
        if not self.api_token or not self.user_data:
            logger.error("Medium API not properly configured")
            return None
        
        try:
            user_id = self.user_data.get('id')
            if not user_id:
                logger.error("User ID not found in Medium API data")
                return None
            
            # Prepare the payload for Medium API
            payload = {
                "title": article_data['title'],
                "contentFormat": "markdown",
                "content": article_data['content'],
                "tags": article_data['tags'][:5],  # Medium allows max 5 tags
                "publishStatus": "draft"  # Start as draft to review before publishing
            }
            
            if article_data.get('subtitle'):
                payload["canonicalUrl"] = article_data['subtitle']
            
            # Make the request to create a post
            post_url = MEDIUM_POST_URL.format(user_id=user_id)
            response = requests.post(post_url, headers=self.headers, json=payload)
            
            if response.status_code == 201:
                post_data = response.json().get('data', {})
                post_id = post_data.get('id')
                post_url = post_data.get('url')
                
                logger.info(f"Article published successfully as draft: {post_url}")
                
                # Update skills history
                skill = article_data['skill']
                if skill not in self.skills_history:
                    self.skills_history[skill] = {}
                
                self.skills_history[skill].update({
                    'last_published': datetime.now().strftime("%Y-%m-%d"),
                    'article_count': self.skills_history.get(skill, {}).get('article_count', 0) + 1,
                    'latest_article': {
                        'title': article_data['title'],
                        'url': post_url,
                        'id': post_id
                    }
                })
                
                # Save updated history
                self._save_published_history()
                
                return post_url
            else:
                logger.error(f"Failed to publish article: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error publishing to Medium: {str(e)}")
            return None
    
    def generate_and_publish_article(self, skill=None):
        """Generate and publish an article for a specific skill or select one"""
        # Select a skill if not specified
        selected_skill = skill or self.select_skill_for_article()
        if not selected_skill:
            logger.error("No skill selected for article generation")
            return None
        
        # Generate the article
        article_data = self.generate_article(selected_skill)
        if not article_data:
            logger.error(f"Failed to generate article for skill: {selected_skill}")
            return None
        
        # Save the article to GCS
        gcs_path = self.save_article(article_data)
        
        # Publish to Medium if API token is configured
        if self.api_token and self.user_data:
            post_url = self.publish_to_medium(article_data)
            if post_url:
                logger.info(f"Article published. Check your Medium drafts and finalize publication: {post_url}")
                return post_url
        else:
            logger.info("Medium API not configured, skipping publication")
        
        return gcs_path


def main():
    """Command-line entry point for medium publisher"""
    parser = argparse.ArgumentParser(description="Generate and publish Medium articles")
    parser.add_argument('--preview', action='store_true', help="Generate without publishing")
    parser.add_argument('--skill', type=str, help="Specify a skill to write about", default=None)
    args = parser.parse_args()
    
    try:
        # Configure Gemini API
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY not set, cannot generate article")
            return 1
        
        # Initialize publisher
        medium = MediumPublisher()
        
        # Generate and optionally publish article
        if args.preview:
            # Just generate and save to GCS
            selected_skill = args.skill or medium.select_skill_for_article()
            if not selected_skill:
                logger.error("No skill selected")
                return 1
            
            article_data = medium.generate_article(selected_skill)
            if article_data:
                gcs_path = medium.save_article(article_data)
                if gcs_path:
                    logger.info(f"Article generated in preview mode: {gcs_path}")
                    print(f"Article generated: {gcs_path}")
                    return 0
            else:
                logger.error("Failed to generate article")
                return 1
        else:
            # Generate and publish
            result = medium.generate_and_publish_article(args.skill)
            if result:
                logger.info(f"Article process completed: {result}")
                print(f"Article process completed: {result}")
                return 0
            else:
                logger.error("Failed to complete article process")
                return 1
    except Exception as e:
        logger.error(f"Error in medium_publisher: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())