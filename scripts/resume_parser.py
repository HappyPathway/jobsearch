import pdfplumber
import re
from pathlib import Path
import sqlite3
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def setup_resume_tables(conn):
    c = conn.cursor()
    
    # Create resume-specific tables
    c.execute('''CREATE TABLE IF NOT EXISTS resume_sections (
        id INTEGER PRIMARY KEY,
        section_name TEXT UNIQUE,
        content TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS resume_experience (
        id INTEGER PRIMARY KEY,
        company TEXT,
        title TEXT,
        start_date TEXT,
        end_date TEXT,
        location TEXT,
        description TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS resume_education (
        id INTEGER PRIMARY KEY,
        institution TEXT,
        degree TEXT,
        field TEXT,
        graduation_date TEXT,
        gpa TEXT
    )''')
    
    conn.commit()

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text() + '\n'
    return text

def clean_json_structure(json_str):
    """Clean and fix common JSON structure issues"""
    # Remove any non-JSON text before the first {
    while not json_str.startswith('{'):
        json_str = json_str[1:]
    
    # Properly escape URLs in the text
    json_str = re.sub(r'(https?://[^\s,"]+)', r'\\"\1\\"', json_str)
    
    # Fix incomplete experience entries
    json_str = re.sub(r'}\s*}\s*]\s*$', '}]}', json_str)
    json_str = re.sub(r'}\s*,\s*}\s*]\s*$', '}]}', json_str)
    
    # Ensure all string values are properly quoted
    def fix_quotes(match):
        key = match.group(1)
        value = match.group(2)
        if not value.startswith('"') and not value.endswith('"'):
            value = f'"{value}"'
        return f'"{key}": {value}'
    
    json_str = re.sub(r'"([^"]+)":\s*([^,}\]]+)', fix_quotes, json_str)
    
    # Balance braces and brackets
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    open_brackets = json_str.count('[')
    close_brackets = json_str.count(']')
    
    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
    
    # Add missing closing braces/brackets
    json_str += '}' * (open_braces - close_braces)
    json_str += ']' * (open_brackets - close_brackets)
    
    return json_str

def parse_resume_text(text):
    """Use Gemini to parse resume text into structured data"""
    prompt = f"""You are a resume parsing system. Parse this text into JSON. 
ONLY return the JSON object itself, no other text, no 'json' prefix, no code block markers.

Text to parse:
{text}

Return this exact structure:
{{
    "summary": "brief career summary",
    "experience": [
        {{
            "company": "name",
            "title": "job title",
            "start_date": "YYYY-MM",
            "end_date": "YYYY-MM or Present",
            "location": "city/remote",
            "description": "key responsibilities and achievements"
        }}
    ],
    "education": [],
    "certifications": []
}}

Rules:
1. Format dates as YYYY-MM (use -01 if month unknown)
2. Use 'Present' for current positions
3. Keep descriptions clear and concise
4. Do not use line breaks in descriptions"""

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1000,
                "temperature": 0.1,
            }
        )
        
        # Clean up the response
        json_str = response.text.strip()
        
        # Remove any non-JSON content
        while not json_str.startswith('{'):
            json_str = json_str[1:]
        while not json_str.endswith('}'):
            json_str = json_str[:-1]
        
        try:
            parsed = json.loads(json_str)
            
            # Normalize experience entries
            for exp in parsed.get('experience', []):
                if not isinstance(exp, dict):
                    continue
                exp['company'] = exp.get('company', '').strip()
                exp['title'] = exp.get('title', '').strip()
                exp['start_date'] = exp.get('start_date', '').strip()
                exp['end_date'] = exp.get('end_date', 'Present').strip()
                exp['location'] = exp.get('location', '').strip()
                # Remove any line breaks in descriptions
                exp['description'] = ' '.join(exp.get('description', '').split())
            
            return parsed
        except json.JSONDecodeError as je:
            print(f"JSON parsing error: {str(je)}")
            print(f"Problematic JSON string: {json_str}")
            return None
            
    except Exception as e:
        print(f"Error parsing resume with Gemini: {str(e)}")
        return None

def save_resume_data(conn, data):
    """Save parsed resume data to database"""
    if not data:
        return
        
    c = conn.cursor()
    
    # Clear existing data
    c.execute("DELETE FROM resume_experience")
    c.execute("DELETE FROM resume_education")
    c.execute("DELETE FROM resume_sections WHERE section_name IN ('summary', 'certifications')")
    
    # Save summary
    if data.get('summary'):
        c.execute("INSERT OR REPLACE INTO resume_sections (section_name, content) VALUES (?, ?)",
                 ('summary', data['summary']))
    
    # Save experiences
    for exp in data.get('experience', []):
        c.execute("""
            INSERT INTO resume_experience (company, title, start_date, end_date, location, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            exp.get('company', ''),
            exp.get('title', ''),
            exp.get('start_date', ''),
            exp.get('end_date', 'Present'),
            exp.get('location', ''),
            exp.get('description', '')
        ))
    
    # Save education
    for edu in data.get('education', []):
        c.execute("""
            INSERT INTO resume_education (institution, degree, field, graduation_date, gpa)
            VALUES (?, ?, ?, ?, ?)
        """, (
            edu.get('institution', ''),
            edu.get('degree', ''),
            edu.get('field', ''),
            edu.get('graduation_date', ''),
            edu.get('gpa', '')
        ))
    
    # Save certifications
    if data.get('certifications'):
        c.execute("INSERT OR REPLACE INTO resume_sections (section_name, content) VALUES (?, ?)",
                 ('certifications', '\n'.join(data['certifications'])))
    
    conn.commit()

def main():
    pdf_path = Path(__file__).parent.parent / 'docs' / 'Resume.pdf'
    if not pdf_path.exists():
        print(f"Error: Resume PDF not found at {pdf_path}")
        return
    
    conn = sqlite3.connect(str(Path(__file__).parent.parent / 'career_data.db'))
    setup_resume_tables(conn)
    
    try:
        # Extract text from PDF
        resume_text = extract_text_from_pdf(pdf_path)
        
        # Use Gemini to parse the text into structured data
        parsed_data = parse_resume_text(resume_text)
        
        # Save the parsed data
        save_resume_data(conn, parsed_data)
        
        print(f"Successfully parsed and saved resume data from {pdf_path}")
        if parsed_data:
            print(f"Found:")
            print(f"- {len(parsed_data.get('experience', []))} experiences")
            print(f"- {len(parsed_data.get('education', []))} education entries")
            print(f"- {len(parsed_data.get('certifications', []))} certifications")
    except Exception as e:
        print(f"Error processing resume: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()