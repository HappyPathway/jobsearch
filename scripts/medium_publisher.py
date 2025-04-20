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

# Add parent directory to Python path to find local modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.logging_utils import setup_logging
from scripts.gcs_utils import GCSUtils

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
    
    def __init__(self, api_token=None):
        """Initialize the Medium Publisher"""
        self.api_token = api_token or MEDIUM_API_TOKEN
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
            root_dir = Path(__file__).resolve().parent.parent
            history_file = os.path.join(root_dir, 'docs', 'medium_history.json')
            
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    self.skills_history = json.load(f)
                logger.info(f"Loaded history for {len(self.skills_history)} skills")
            else:
                logger.info("No history file found, creating new one")
                self.skills_history = {}
            
            return self.skills_history
        except Exception as e:
            logger.error(f"Error loading publication history: {str(e)}")
            return {}
    
    def _save_published_history(self):
        """Save history of published articles"""
        try:
            root_dir = Path(__file__).resolve().parent.parent
            history_file = os.path.join(root_dir, 'docs', 'medium_history.json')
            
            with open(history_file, 'w') as f:
                json.dump(self.skills_history, f, indent=2)
            
            logger.info(f"Saved history for {len(self.skills_history)} skills")
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
            
            # First, get an outline for the article
            outline_prompt = f"""You are an expert writer specializing in {skill} as it relates to the field of {domain}.
Create a detailed outline for a professional blog post about {skill}. 
The article should demonstrate expertise and provide value to other professionals in this or related fields.
Include sections for introduction, key concepts, practical applications, examples if relevant, and conclusion.
Format as a JSON object like this:
{{
    "title": "Suggested title for the article",
    "subtitle": "Compelling subtitle to engage readers",
    "sections": [
        {{
            "heading": "Introduction",
            "bullet_points": [
                "Key point 1",
                "Key point 2"
            ]
        }},
        {{
            "heading": "Section name",
            "bullet_points": [
                "Detail 1",
                "Detail 2"
            ]
        }}
    ],
    "tags": ["suggested", "tags", "for", "medium"]
}}"""
            
            model = genai.GenerativeModel('gemini-1.5-pro')
            outline_response = model.generate_content(
                outline_prompt,
                generation_config={
                    "max_output_tokens": 2000,
                    "temperature": 0.2,
                }
            )
            
            # Clean up the response and extract JSON
            outline_text = outline_response.text.strip()
            outline_text = outline_text.replace('```json', '').replace('```', '')
            
            try:
                outline = json.loads(outline_text)
                logger.info(f"Generated outline with {len(outline['sections'])} sections")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse outline JSON: {outline_text[:100]}...")
                return None
            
            # Now, generate the full article based on the outline
            article_prompt = f"""You are an expert writer specializing in {skill} as it relates to the field of {domain}.
Write a comprehensive, engaging, and well-informed blog post about {skill} using this outline:
{json.dumps(outline, indent=2)}

The article should:
1. Show deep expertise (this will be published on Medium to demonstrate professional knowledge)
2. Include practical examples relevant to the {domain} field
3. Use Markdown formatting
4. Have a professional but engaging tone
5. Be well-structured with clear headings (use # for main heading, ## for section headings)
6. Be between 1000-1500 words
7. Include a brief author bio at the end that mentions you're a {domain} professional seeking new opportunities

Title your post using the suggested title from the outline."""
            
            article_response = model.generate_content(
                article_prompt,
                generation_config={
                    "max_output_tokens": 8000,
                    "temperature": 0.3,
                }
            )
            
            article_content = article_response.text.strip()
            
            # Extract title for return value
            title = outline.get('title', f"Professional Guide to {skill}")
            
            # Generate appropriate tags based on the domain and skill
            default_tags = [skill, domain, "Career Development", "Professional Growth"]
            
            # Create the complete article data
            article_data = {
                'title': title,
                'subtitle': outline.get('subtitle', f"Essential insights into {skill} for professionals in {domain}"),
                'content': article_content,
                'tags': outline.get('tags', default_tags),
                'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'skill': skill,
                'domain': domain
            }
            
            logger.info(f"Generated article: {article_data['title']} ({len(article_content)} chars)")
            return article_data
        except Exception as e:
            logger.error(f"Error generating article: {str(e)}")
            return None
    
    def save_article_locally(self, article_data):
        """Save the generated article locally"""
        try:
            if not article_data:
                logger.error("No article data to save")
                return None
            
            root_dir = Path(__file__).resolve().parent.parent
            articles_dir = os.path.join(root_dir, 'articles')
            
            # Create articles directory if it doesn't exist
            if not os.path.exists(articles_dir):
                os.makedirs(articles_dir)
                logger.info(f"Created articles directory at {articles_dir}")
            
            # Create filename from title and date
            date_str = datetime.now().strftime("%Y-%m-%d")
            title_slug = article_data['title'].lower().replace(" ", "-")
            title_slug = ''.join(c for c in title_slug if c.isalnum() or c == '-')
            
            md_filename = f"{date_str}_{title_slug}.md"
            json_filename = f"{date_str}_{title_slug}.json"
            
            md_path = os.path.join(articles_dir, md_filename)
            json_path = os.path.join(articles_dir, json_filename)
            
            # Save as markdown
            with open(md_path, 'w') as f:
                f.write(article_data['content'])
            
            # Save metadata as JSON
            with open(json_path, 'w') as f:
                json.dump(article_data, f, indent=2)
            
            logger.info(f"Article saved to {md_path}")
            logger.info(f"Metadata saved to {json_path}")
            
            return md_path
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
        
        # Save the article locally
        local_path = self.save_article_locally(article_data)
        
        # Update GCS if configured
        try:
            if GCS_BUCKET_NAME:
                gcs = GCSUtils(GCS_BUCKET_NAME)
                gcs.upload_file(local_path)
                logger.info(f"Uploaded article to GCS: {os.path.basename(local_path)}")
        except Exception as e:
            logger.warning(f"Failed to upload article to GCS: {str(e)}")
        
        # Publish to Medium if API token is configured
        if self.api_token and self.user_data:
            post_url = self.publish_to_medium(article_data)
            if post_url:
                logger.info(f"Article published. Check your Medium drafts and finalize publication: {post_url}")
                return post_url
        else:
            logger.info("Medium API not configured, skipping publication")
        
        return local_path


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
            # Just generate and save locally
            selected_skill = args.skill or medium.select_skill_for_article()
            if not selected_skill:
                logger.error("No skill selected")
                return 1
            
            article_data = medium.generate_article(selected_skill)
            if article_data:
                local_path = medium.save_article_locally(article_data)
                if local_path:
                    logger.info(f"Article generated in preview mode: {local_path}")
                    print(f"Article generated: {local_path}")
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