import logging
import re
from datetime import datetime
from dotenv import load_dotenv
import os
import json
import google.generativeai as genai
from models import Experience, Skill, TargetRole, get_session

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def fetch_data():
    """Get experiences and skills from database using SQLAlchemy"""
    with get_session() as session:
        linkedin_exp = session.query(Experience).order_by(Experience.start_date.desc()).all()
        linkedin_exp = [
            (exp.company, exp.title, exp.start_date, exp.end_date, exp.description)
            for exp in linkedin_exp
        ]
        
        skills = session.query(Skill).all()
        skill_names = [skill.skill_name for skill in skills]
        
        return linkedin_exp, skill_names

def format_experiences(exps):
    out = []
    for e in exps:
        # e: (company, title, start_date, end_date, description)
        out.append(f"- **{e[1]}** at **{e[0]}** ({e[2]} - {e[3]}): {e[4]}")
    return "\n".join(out)

def generate_target_roles(experiences, skills):
    """Use Gemini to generate and score target roles based on profile data"""
    prompt = f"""You are an expert career advisor with deep knowledge of tech industry roles.
Analyze this professional's background and generate appropriate target roles.
Return ONLY a JSON array with no additional text or formatting.

Experience:
{format_experiences(experiences)}

Skills: {', '.join(skills)}

Return this format:
[
    {{
        "role_name": "exact job title",
        "priority": 1,
        "match_score": 95.0,
        "reasoning": "detailed explanation of fit",
        "source": "derived from current experience"
    }},
    // ... more roles ...
]

Notes:
1. priority should be 1-5 (1 is highest)
2. match_score should be 0-100
3. Be specific with role names
4. Focus on senior/principal level roles
5. Consider cloud, DevOps, and platform engineering roles"""

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 1000,
                "temperature": 0.2,
            }
        )
        
        json_str = response.text.strip()
        json_str = json_str.replace('```json', '').replace('```', '')
        
        # Try to extract just the JSON array
        match = re.search(r'(\[[\s\S]*\])', json_str)
        if match:
            json_str = match.group(1)
        
        roles = json.loads(json_str)
        
        # Validate and normalize
        for role in roles:
            role['priority'] = max(1, min(5, int(role.get('priority', 5))))
            role['match_score'] = max(0, min(100, float(role.get('match_score', 0))))
            role['role_name'] = str(role.get('role_name', '')).strip()
            role['reasoning'] = str(role.get('reasoning', '')).strip()
            role['source'] = str(role.get('source', 'AI generated')).strip()
        
        return roles
    except Exception as e:
        logger.error(f"Error generating target roles: {str(e)}")
        return []

def update_target_roles(roles):
    """Update target roles in the database"""
    if not roles:
        return
        
    with get_session() as session:
        # Clear existing roles
        session.query(TargetRole).delete()
        
        # Add new roles
        for role in roles:
            target_role = TargetRole(
                role_name=role['role_name'],
                priority=role['priority'],
                match_score=role['match_score'],
                reasoning=role['reasoning'],
                source=role['source'],
                last_updated=datetime.now().strftime("%Y-%m-%d")
            )
            session.add(target_role)
        
        logger.info(f"Successfully updated {len(roles)} target roles")

def main():
    try:
        logger.info("Generating target roles from profile data")
        experiences, skills = fetch_data()
        roles = generate_target_roles(experiences, skills)
        logger.info("Updating target roles in database")
        update_target_roles(roles)
        logger.info("Successfully updated target roles")
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    main()
