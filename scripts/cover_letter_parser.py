import pdfplumber
from pathlib import Path
import sqlite3
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def setup_cover_letter_tables(conn):
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS cover_letter_sections (
        id INTEGER PRIMARY KEY,
        section_name TEXT UNIQUE,
        content TEXT
    )''')
    
    conn.commit()

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        for page in pdf.pages:
            text += page.extract_text() + '\n'
    return text

def parse_cover_letter_text(text):
    """Use Gemini to parse cover letter text into structured data"""
    prompt = f"""You are a cover letter parsing system. Parse this text into JSON.
ONLY return the JSON object itself, no other text, no prefixes, no code block markers.

Text to parse:
{text}

Return this exact structure:
{{
    "greeting": "greeting text",
    "introduction": "first paragraph introducing the candidate",
    "body": [
        "paragraph 1 discussing skills and experience",
        "paragraph 2 discussing qualifications",
        "etc..."
    ],
    "closing": "closing paragraph",
    "signature": "signature text",
    "key_points": [
        "main point 1",
        "main point 2",
        "etc..."
    ]
}}

Rules:
1. Preserve the original content but split into logical sections
2. Extract 3-5 key points that make this candidate stand out
3. Do not add information that isn't in the original text
4. Keep paragraphs in their original order"""

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
            
        return json.loads(json_str)
    except Exception as e:
        print(f"Error parsing cover letter with Gemini: {str(e)}")
        return None

def save_cover_letter_data(conn, data):
    """Save parsed cover letter data to database"""
    if not data:
        return
        
    c = conn.cursor()
    
    # Clear existing data
    c.execute("DELETE FROM cover_letter_sections")
    
    # Save greeting
    if data.get('greeting'):
        c.execute("INSERT INTO cover_letter_sections (section_name, content) VALUES (?, ?)",
                 ('greeting', data['greeting']))
    
    # Save introduction
    if data.get('introduction'):
        c.execute("INSERT INTO cover_letter_sections (section_name, content) VALUES (?, ?)",
                 ('introduction', data['introduction']))
    
    # Save body paragraphs
    if data.get('body'):
        c.execute("INSERT INTO cover_letter_sections (section_name, content) VALUES (?, ?)",
                 ('body', '\n\n'.join(data['body'])))
    
    # Save closing
    if data.get('closing'):
        c.execute("INSERT INTO cover_letter_sections (section_name, content) VALUES (?, ?)",
                 ('closing', data['closing']))
    
    # Save signature
    if data.get('signature'):
        c.execute("INSERT INTO cover_letter_sections (section_name, content) VALUES (?, ?)",
                 ('signature', data['signature']))
    
    # Save key points
    if data.get('key_points'):
        c.execute("INSERT INTO cover_letter_sections (section_name, content) VALUES (?, ?)",
                 ('key_points', '\n'.join(data['key_points'])))
    
    conn.commit()

def main():
    pdf_path = Path(__file__).parent.parent / 'docs' / 'CoverLetter.pdf'
    if not pdf_path.exists():
        print(f"Error: Cover Letter PDF not found at {pdf_path}")
        return
    
    conn = sqlite3.connect(str(Path(__file__).parent.parent / 'career_data.db'))
    setup_cover_letter_tables(conn)
    
    try:
        # Extract text from PDF
        cover_letter_text = extract_text_from_pdf(pdf_path)
        
        # Use Gemini to parse into structured data
        parsed_data = parse_cover_letter_text(cover_letter_text)
        
        # Save the parsed data
        save_cover_letter_data(conn, parsed_data)
        
        print(f"Successfully parsed and saved cover letter data from {pdf_path}")
        if parsed_data:
            print(f"Found:")
            print(f"- {len(parsed_data.get('body', []))} body paragraphs")
            print(f"- {len(parsed_data.get('key_points', []))} key points")
    except Exception as e:
        print(f"Error processing cover letter: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()