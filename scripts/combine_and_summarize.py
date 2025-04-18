import sqlite3
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def fetch_data():
    conn = sqlite3.connect('career_data.db')
    c = conn.cursor()
    c.execute("SELECT company, title, start_date, end_date, description FROM experiences")
    linkedin_exp = c.fetchall()
    c.execute("SELECT company, title, start_date, end_date, location, description FROM resume_experience")
    resume_exp = c.fetchall()
    c.execute("SELECT skill_name FROM skills")
    linkedin_skills = [row[0] for row in c.fetchall()]
    conn.close()
    return linkedin_exp, resume_exp, linkedin_skills

def format_experiences(exps):
    out = []
    for e in exps:
        # e: (company, title, start_date, end_date, description)
        out.append(f"- **{e[1]}** at **{e[0]}** ({e[2]} - {e[3]}): {e[4]}")
    return "\n".join(out)

def format_resume_experiences(exps):
    out = []
    for e in exps:
        # e: (company, title, start_date, end_date, location, description)
        loc = f", {e[4]}" if e[4] else ""
        out.append(f"- **{e[1]}** at **{e[0]}** ({e[2]} - {e[3]}{loc}): {e[5]}")
    return "\n".join(out)

def generate_target_roles(experiences, skills):
    """Use Gemini to generate and score target roles based on profile data"""
    logger.info("Generating target roles from profile data")
    
    prompt = f"""As a career strategist, analyze this professional's background and generate a prioritized list of target roles.
Focus on roles that match their experience level and skill set.

Experience:
{format_experiences(experiences)}

Skills:
{', '.join(skills)}

Return a JSON array of role objects with this structure:
[
    {{
        "role_name": "exact job title to search for",
        "priority": 1,
        "match_score": 95.5,
        "reasoning": "brief explanation of why this role is a good fit"
    }}
]

Rules:
1. Return 5-8 roles
2. Priority should be 1-8 (1 is highest)
3. Match score should be 0-100
4. Focus on senior/principal level roles
5. Include both exact current role matches and logical next-step roles
6. Consider industry trends and career progression
7. Roles should be specific enough to use as search terms"""

    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1000,
                "temperature": 0.2,
            }
        )
        
        json_str = response.text.strip()
        while not json_str.startswith('['):
            json_str = json_str[1:]
        while not json_str.endswith(']'):
            json_str = json_str[:-1]
            
        roles = json.loads(json_str)
        return roles
    except Exception as e:
        logger.error(f"Error generating target roles: {str(e)}")
        return []

def update_target_roles(conn, roles):
    """Update target roles in the database"""
    logger.info("Updating target roles in database")
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # Clear existing roles
        c.execute("DELETE FROM target_roles")
        
        # Insert new roles
        for role in roles:
            c.execute("""
                INSERT INTO target_roles 
                    (role_name, priority, match_score, reasoning, source, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                role['role_name'],
                role['priority'],
                role['match_score'],
                role['reasoning'],
                'profile_analysis',
                today
            ))
        
        conn.commit()
        logger.info(f"Successfully updated {len(roles)} target roles")
    except Exception as e:
        logger.error(f"Error updating target roles: {str(e)}")
        conn.rollback()

def main():
    conn = sqlite3.connect('career_data.db')
    try:
        linkedin_exp, resume_exp, linkedin_skills = fetch_data()
        
        # Generate combined profile
        prompt = f"""
You are an expert career coach and resume writer. Given the following LinkedIn experiences, resume experiences, and LinkedIn skills, intelligently merge and deduplicate the experiences, summarize the candidate's background, and generate a recruiter-friendly professional summary. Highlight strengths, key skills, and suggest what types of jobs would be a great fit.

LinkedIn Experiences:
{format_experiences(linkedin_exp)}

Resume Experiences:
{format_resume_experiences(resume_exp)}

LinkedIn Skills:
{', '.join(linkedin_skills)}

Please output:
1. A unified, deduplicated list of experiences (in bullet points)
2. A summary of top skills
3. A professional summary paragraph suitable for a recruiter or LinkedIn "About" section
4. 3-5 suggested job titles that would be a strong fit
"""

        try:
            model = genai.GenerativeModel("gemini-1.5-pro")
            response = model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": 1000,
                    "temperature": 0.5,
                }
            )
            output = response.text
            
            # Generate and update target roles
            roles = generate_target_roles(linkedin_exp, linkedin_skills)
            update_target_roles(conn, roles)
            
            with open("combined_profile.md", "w") as f:
                f.write(output)
            logger.info("Combined profile written to combined_profile.md")
        except Exception as e:
            logger.error(f"Error generating combined profile: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
