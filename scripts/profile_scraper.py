import pdfplumber
import sqlite3
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re
from utils import setup_logging

logger = setup_logging('profile_scraper')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class ProfileScraper:
    def __init__(self):
        logger.info("Initializing ProfileScraper")
    
    def scrape(self, url):
        logger.info(f"Starting profile scrape for URL: {url}")
        try:
            # Scraping logic here
            logger.debug(f"Successfully scraped data from {url}")
        except Exception as e:
            logger.error(f"Error scraping profile from {url}: {str(e)}")
            raise
    
    def parse(self, content):
        logger.debug("Parsing scraped content")
        try:
            # Parsing logic here
            logger.debug("Successfully parsed profile content")
        except Exception as e:
            logger.error(f"Error parsing profile content: {str(e)}")
            raise

    def save(self, data):
        logger.info("Saving scraped profile data")
        try:
            # Saving logic here
            logger.info("Successfully saved profile data")
        except Exception as e:
            logger.error(f"Error saving profile data: {str(e)}")
            raise

def setup_database():
    conn = sqlite3.connect('career_data.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS experiences (
        id INTEGER PRIMARY KEY,
        company TEXT,
        title TEXT,
        start_date TEXT,
        end_date TEXT,
        description TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY,
        skill_name TEXT UNIQUE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS experience_skills (
        experience_id INTEGER,
        skill_id INTEGER,
        FOREIGN KEY (experience_id) REFERENCES experiences (id),
        FOREIGN KEY (skill_id) REFERENCES skills (id)
    )''')
    
    conn.commit()
    return conn

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    logger.info(f"Extracting text from PDF: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() + '\n'
            logger.info(f"Successfully extracted {len(text)} characters from PDF")
            return text
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {str(e)}")
        raise

def parse_profile_text(text):
    """Use Gemini to parse LinkedIn profile text into structured data"""
    logger.info("Starting profile text parsing with Gemini")
    prompt = f"""Parse this text into a single line of JSON with no line breaks.
Output only the JSON object, nothing else.

Text to parse:
{text}

Example format (single line, replace with actual data):
{{"experiences":[{{"company":"Company","title":"Title","start_date":"2020-01","end_date":"Present","description":"Work description"}}],"skills":["Skill1"],"certifications":[],"education":[{{"school":"School","degree":"Degree","field":"Field","start_date":"2020-01","end_date":"2020-12"}}]}}

Rules:
1. Output must be a single line of valid JSON
2. Use double quotes for all strings
3. No trailing commas
4. No line breaks or formatting
5. Format dates as YYYY-MM
6. Use 'Present' for current positions
7. Keep descriptions concise
8. Extract key skills
9. Only include stated certifications
10. Only include information from the text"""

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        logger.debug("Sending text to Gemini for parsing")
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.1,
            }
        )
        
        # Clean up the response
        json_str = response.text.strip()
        logger.debug("Received response from Gemini")
        
        # Extract just the JSON object
        match = re.search(r'({.*})', json_str)
        if match:
            json_str = match.group(1)
        
        # Basic cleanup
        json_str = json_str.replace('\n', ' ').replace('\r', ' ')
        json_str = re.sub(r'\s+', ' ', json_str)
        
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {str(e)}")
            return None
        
        # Normalize and validate data
        logger.info("Normalizing parsed data")
        normalized = {
            "experiences": [],
            "skills": [],
            "certifications": [],
            "education": []
        }
        
        # Normalize experiences
        for exp in parsed.get('experiences', []):
            if isinstance(exp, dict):
                normalized["experiences"].append({
                    "company": str(exp.get('company', '')).strip(),
                    "title": str(exp.get('title', '')).strip(),
                    "start_date": str(exp.get('start_date', '')).strip(),
                    "end_date": str(exp.get('end_date', 'Present')).strip(),
                    "description": ' '.join(str(exp.get('description', '')).split())
                })
        
        # Normalize lists
        normalized["skills"] = [str(s).strip() for s in parsed.get('skills', []) if s]
        normalized["certifications"] = [str(c).strip() for c in parsed.get('certifications', []) if c]
        
        # Normalize education
        for edu in parsed.get('education', []):
            if isinstance(edu, dict):
                normalized["education"].append({
                    "school": str(edu.get('school', '')).strip(),
                    "degree": str(edu.get('degree', '')).strip(),
                    "field": str(edu.get('field', '')).strip() if edu.get('field') else '',
                    "start_date": str(edu.get('start_date', '')).strip(),
                    "end_date": str(edu.get('end_date', '')).strip()
                })
        
        logger.info(f"Successfully parsed profile data: {len(normalized['experiences'])} experiences, {len(normalized['skills'])} skills")
        return normalized
    except Exception as e:
        logger.error(f"Error parsing profile with Gemini: {str(e)}")
        return None

def save_to_database(conn, parsed_data):
    """Save parsed profile data to database"""
    if not parsed_data:
        logger.warning("No parsed data to save to database")
        return
        
    logger.info("Saving parsed data to database")
    c = conn.cursor()
    
    try:
        # Clear existing data
        c.execute("DELETE FROM experiences")
        c.execute("DELETE FROM skills")
        c.execute("DELETE FROM experience_skills")
        logger.debug("Cleared existing data from database")
        
        # Save skills first to get their IDs
        skill_count = 0
        skill_ids = {}
        for skill in parsed_data.get('skills', []):
            c.execute("INSERT OR IGNORE INTO skills (skill_name) VALUES (?)", (skill,))
            c.execute("SELECT id FROM skills WHERE skill_name = ?", (skill,))
            skill_ids[skill] = c.fetchone()[0]
            skill_count += 1
        logger.info(f"Saved {skill_count} skills to database")
        
        # Save experiences and link skills
        exp_count = 0
        for exp in parsed_data.get('experiences', []):
            c.execute("""
                INSERT INTO experiences (company, title, start_date, end_date, description)
                VALUES (?, ?, ?, ?, ?)
            """, (
                exp.get('company', ''),
                exp.get('title', ''),
                exp.get('start_date', ''),
                exp.get('end_date', 'Present'),
                exp.get('description', '')
            ))
            
            exp_id = c.lastrowid
            exp_count += 1
            
            # Link skills mentioned in the description
            skill_links = 0
            for skill, skill_id in skill_ids.items():
                if skill.lower() in exp.get('description', '').lower():
                    c.execute("""
                        INSERT INTO experience_skills (experience_id, skill_id)
                        VALUES (?, ?)
                    """, (exp_id, skill_id))
                    skill_links += 1
            logger.debug(f"Linked {skill_links} skills to experience '{exp.get('title')}'")
        
        logger.info(f"Saved {exp_count} experiences to database")
        conn.commit()
        logger.info("Successfully committed all data to database")
    except Exception as e:
        logger.error(f"Error saving to database: {str(e)}")
        conn.rollback()
        raise

def main():
    pdf_path = Path(__file__).parent.parent / 'docs' / 'Profile.pdf'
    logger.info(f"Starting profile scraping process")
    
    if not pdf_path.exists():
        logger.error(f"Error: LinkedIn profile PDF not found at {pdf_path}")
        return
    
    conn = setup_database()
    logger.info("Database connection established")
    
    try:
        # Extract text from PDF
        profile_text = extract_text_from_pdf(pdf_path)
        
        # Use Gemini to parse into structured data
        parsed_data = parse_profile_text(profile_text)
        
        # Save the parsed data
        save_to_database(conn, parsed_data)
        
        logger.info(f"Successfully completed profile scraping process")
        if parsed_data:
            logger.info(f"Summary of processed data:")
            logger.info(f"- {len(parsed_data.get('experiences', []))} experiences")
            logger.info(f"- {len(parsed_data.get('skills', []))} skills")
            logger.info(f"- {len(parsed_data.get('certifications', []))} certifications")
            logger.info(f"- {len(parsed_data.get('education', []))} education entries")
    except Exception as e:
        logger.error(f"Error processing profile: {str(e)}")
    finally:
        conn.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    main()