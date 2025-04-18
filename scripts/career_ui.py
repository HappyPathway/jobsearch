from flask import Flask, render_template, jsonify, request
import sqlite3
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

def get_db():
    db_path = Path(__file__).parent.parent / 'career_data.db'
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/experiences')
def get_experiences():
    conn = get_db()
    cursor = conn.cursor()
    
    # Get LinkedIn experiences
    cursor.execute("""
        SELECT company, title, start_date, end_date, description 
        FROM experiences 
        ORDER BY start_date DESC
    """)
    linkedin_experiences = [dict(row) for row in cursor.fetchall()]
    
    # Get Resume experiences
    cursor.execute("""
        SELECT company, title, start_date, end_date, location, description 
        FROM resume_experience 
        ORDER BY start_date DESC
    """)
    resume_experiences = [dict(row) for row in cursor.fetchall()]
    
    conn.close()

    # Use Gemini to generate a cohesive summary
    def format_exp(exps):
        out = []
        for e in exps:
            loc = f", {e.get('location','')}" if 'location' in e and e.get('location') else ''
            out.append(f"- {e['title']} at {e['company']} ({e['start_date']} - {e['end_date']}{loc}): {e['description']}")
        return "\n".join(out)

    prompt = f"""
You are an expert career coach. Given the following LinkedIn and resume experiences, write a cohesive, recruiter-friendly summary that highlights the candidate's career progression, strengths, and impact. Avoid repetition and make it flow as a narrative. Limit to 2-3 paragraphs.

LinkedIn Experiences:
{format_exp(linkedin_experiences)}

Resume Experiences:
{format_exp(resume_experiences)}
"""
    summary = ""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 600,  # Increased for better summaries
                "temperature": 0.4,        # Reduced for more focused, factual content
            }
        )
        summary = response.text.strip()
    except Exception as e:
        summary = "AI summary unavailable. (" + str(e) + ")"

    return jsonify({
        'linkedin': linkedin_experiences,
        'resume': resume_experiences,
        'summary': summary
    })

@app.route('/api/skills')
def get_skills():
    conn = get_db()
    cursor = conn.cursor()
    
    # Only get LinkedIn skills
    cursor.execute("SELECT skill_name FROM skills")
    skills = [row['skill_name'] for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({'skills': skills})

@app.route('/api/sections')
def get_sections():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT section_name, content FROM resume_sections")
    sections = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify(sections)

@app.route('/api/keywords')
def get_keywords():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT company, title, start_date, end_date, description FROM experiences")
    linkedin_experiences = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT company, title, start_date, end_date, location, description FROM resume_experience")
    resume_experiences = [dict(row) for row in cursor.fetchall()]
    conn.close()

    def format_exp(exps):
        out = []
        for e in exps:
            loc = f", {e.get('location','')}" if 'location' in e and e.get('location') else ''
            out.append(f"- {e['title']} at {e['company']} ({e['start_date']} - {e['end_date']}{loc}): {e['description']}")
        return "\n".join(out)

    prompt = f"""
You are an expert technical recruiter. Given the following LinkedIn and resume experiences, extract a list of the most important and relevant keywords and phrases that recruiters would search for when looking for candidates like this. Focus on technologies, methodologies, certifications, industries, and job functions. Return a comma-separated list of keywords and phrases, ordered by relevance and importance.

LinkedIn Experiences:
{format_exp(linkedin_experiences)}

Resume Experiences:
{format_exp(resume_experiences)}
"""
    keywords = ""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 300,  # Increased slightly for more comprehensive keywords
                "temperature": 0.3,        # Reduced for more deterministic, focused keywords
            }
        )
        keywords = response.text.strip()
    except Exception as e:
        keywords = "AI keyword extraction unavailable. (" + str(e) + ")"

    return jsonify({'keywords': keywords})

@app.route('/api/complimentary_keywords')
def get_complimentary_keywords():
    # Get the current recruiter keywords
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT skill_name FROM skills")
    skills = [row['skill_name'] for row in cursor.fetchall()]
    conn.close()
    # Use Gemini to generate complimentary keywords
    prompt = f"""
You are an expert technical recruiter. Here is a list of keywords that describe a candidate's skills and experience:

{', '.join(skills)}

List other keywords and phrases that recruiters would commonly expect to see on profiles with these keywords, but which are not already in the list. Focus on technologies, certifications, methodologies, and job functions that are highly complimentary or adjacent. Return a comma-separated list of these complimentary keywords, ordered by relevance.
"""
    complimentary = ""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 300,  # Increased slightly for more comprehensive keywords
                "temperature": 0.3,        # Reduced for more deterministic, focused keywords
            }
        )
        complimentary = response.text.strip()
    except Exception as e:
        complimentary = "AI complimentary keyword extraction unavailable. (" + str(e) + ")"
    return jsonify({'complimentary_keywords': complimentary})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8088)