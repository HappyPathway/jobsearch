import pdfplumber
import sqlite3
import re
from pathlib import Path

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

def parse_linkedin_pdf(pdf_path):
    experiences = []
    skills = []
    current_section = None
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            lines = text.split('\n')
            
            current_exp = None
            for line in lines:
                line = line.strip()
                
                # Detect sections
                if any(section in line.lower() for section in ['experience', 'skills & endorsements', 'skills']):
                    current_section = 'skills' if 'skills' in line.lower() else 'experience'
                    continue
                
                if current_section == 'experience':
                    # Look for dates as they often indicate the start of a new experience
                    date_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|[0-9]{4}).*?-.*?(Present|[0-9]{4})', line)
                    
                    if date_match:
                        # Save previous experience if exists
                        if current_exp:
                            experiences.append(current_exp)
                        current_exp = {'dates': line}
                    elif current_exp:
                        # If we have a current experience, add to its description
                        if 'title' not in current_exp:
                            current_exp['title'] = line
                        elif 'company' not in current_exp:
                            current_exp['company'] = line
                        elif 'description' not in current_exp:
                            current_exp['description'] = line
                        else:
                            current_exp['description'] += ' ' + line
                
                elif current_section == 'skills':
                    # Skip header-like lines and common LinkedIn text
                    if line and not any(x in line.lower() for x in ['skills', 'endorsements', 'see more', 'show more']):
                        # Clean and normalize skill text
                        skill = re.sub(r'\([^)]*\)', '', line).strip()  # Remove parenthetical text
                        if skill and len(skill) > 1:
                            if ',' in skill:
                                # Handle comma-separated skills
                                for s in skill.split(','):
                                    s = s.strip()
                                    if s and len(s) > 1 and not any(x in s.lower() for x in ['see more', 'show more']):
                                        skills.append(s)
                            else:
                                skills.append(skill)

            # Add the last experience if any
            if current_exp:
                experiences.append(current_exp)
    
    # Clean up experiences
    for exp in experiences:
        if 'description' not in exp:
            exp['description'] = ''
        if 'company' not in exp:
            exp['company'] = 'Unknown Company'
        if 'title' not in exp:
            exp['title'] = 'Unknown Title'
    
    # Remove duplicates while preserving order
    skills = list(dict.fromkeys(skills))
    
    return experiences, skills

def save_to_database(conn, experiences, skills):
    c = conn.cursor()
    
    # Save skills
    for skill in skills:
        c.execute("INSERT OR IGNORE INTO skills (skill_name) VALUES (?)", (skill,))
    
    # Save experiences and link skills
    for exp in experiences:
        dates = exp.get('dates', '').split(' - ') if ' - ' in exp.get('dates', '') else ['', 'Present']
        c.execute("""
            INSERT INTO experiences (company, title, start_date, end_date, description)
            VALUES (?, ?, ?, ?, ?)
        """, (exp.get('company', ''), exp.get('title', ''), dates[0], dates[1], exp.get('description', '')))
        
        exp_id = c.lastrowid
        
        # Link relevant skills to experience based on description
        for skill in skills:
            if skill.lower() in exp.get('description', '').lower():
                c.execute("""
                    INSERT INTO experience_skills (experience_id, skill_id)
                    SELECT ?, id FROM skills WHERE skill_name = ?
                """, (exp_id, skill))
    
    conn.commit()

def main():
    pdf_path = Path(__file__).parent.parent / 'docs' / 'Profile.pdf'
    if not pdf_path.exists():
        print(f"Error: LinkedIn profile PDF not found at {pdf_path}")
        return
        
    conn = setup_database()
    experiences, skills = parse_linkedin_pdf(pdf_path)
    
    if experiences or skills:
        save_to_database(conn, experiences, skills)
        print(f"Successfully parsed and saved data from {pdf_path}")
        print(f"Found {len(experiences)} experiences and {len(skills)} skills")
    else:
        print("No data was extracted from the PDF. Please check if the PDF format is correct")
    
    conn.close()

if __name__ == "__main__":
    main()