import logging
import re
from datetime import datetime
from dotenv import load_dotenv
import os
import json
import google.generativeai as genai
from jobsearch.core.database import Experience, Skill, TargetRole, get_session
from jobsearch.core.ai import StructuredPrompt

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def fetch_data():
    """Get experiences, skills, and existing target roles from database using SQLAlchemy"""
    with get_session() as session:
        linkedin_exp = session.query(Experience).order_by(Experience.start_date.desc()).all()
        linkedin_exp = [
            (exp.company, exp.title, exp.start_date, exp.end_date, exp.description)
            for exp in linkedin_exp
        ]
        
        skills = session.query(Skill).all()
        skill_names = [skill.skill_name for skill in skills]
        
        # Fetch existing target roles
        existing_roles = session.query(TargetRole).order_by(TargetRole.priority).all()
        target_roles = [
            {
                "role_name": role.role_name,
                "priority": role.priority,
                "match_score": role.match_score
            }
            for role in existing_roles
        ]
        
        return linkedin_exp, skill_names, target_roles

def format_experiences(exps):
    out = []
    for e in exps:
        # e: (company, title, start_date, end_date, description)
        out.append(f"- **{e[1]}** at **{e[0]}** ({e[2]} - {e[3]}): {e[4]}")
    return "\n".join(out)

def generate_target_roles(experiences, skills, existing_roles):
    """Use Gemini to generate and score target roles based on profile data"""
    roles_str = "\n".join([f"- {r['role_name']} (Priority: {r['priority']}, Match: {r['match_score']}%)" 
                          for r in existing_roles]) if existing_roles else "No existing roles"
    
    # Initialize StructuredPrompt
    structured_prompt = StructuredPrompt()

    # Define expected structure
    expected_structure = [{
        "role_name": str,
        "priority": int,
        "match_score": float,
        "reasoning": str,
        "source": str,
        "requirements": [str],
        "next_steps": [str]
    }]

    # Example data
    example_data = [{
        "role_name": "Senior Cloud Architect",
        "priority": 1,
        "match_score": 85.5,
        "reasoning": "Strong match for cloud infrastructure and system design experience",
        "source": "AI generated",
        "requirements": [
            "Experience with major cloud platforms",
            "Strong system design skills"
        ],
        "next_steps": [
            "Highlight cloud migration projects",
            "Showcase architecture decisions"
        ]
    }]

    # Get structured response
    roles = structured_prompt.get_structured_response(
        prompt=f"""You are an expert career advisor with deep knowledge of tech industry roles.
Analyze this professional's background and generate appropriate target roles.

Current target roles being considered:
{roles_str}

Experience:
{format_experiences(experiences)}

Skills: {', '.join(skills)}

Focus on senior/principal level roles in cloud, DevOps, and platform engineering.
Generate 3-5 role recommendations.

Each role should have:
1. Clear job title that matches real job postings
2. Priority (1-5, where 1 is highest)
3. Match score (0-100)
4. Brief reasoning for the recommendation
5. Key requirements needed
6. Next steps to strengthen candidacy""",
        expected_structure=expected_structure,
        example_data=example_data
    )

    if not roles:
        logger.error("Failed to generate target roles")
        return []

    # Validate and normalize each role
    for role in roles:
        # Required fields
        role['role_name'] = str(role.get('role_name', '')).strip()
        role['priority'] = max(1, min(5, int(role.get('priority', 5))))
        role['match_score'] = max(0, min(100, float(role.get('match_score', 0))))
        role['reasoning'] = str(role.get('reasoning', '')).strip()
        role['source'] = str(role.get('source', 'AI generated')).strip()
        
        # Optional fields with defaults
        if 'requirements' not in role:
            role['requirements'] = []
        if 'next_steps' not in role:
            role['next_steps'] = []
            
        # Ensure lists contain strings
        role['requirements'] = [str(req).strip() for req in role['requirements']]
        role['next_steps'] = [str(step).strip() for step in role['next_steps']]
    
    return roles

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
        experiences, skills, existing_roles = fetch_data()
        roles = generate_target_roles(experiences, skills, existing_roles)
        logger.info("Updating target roles in database")
        update_target_roles(roles)
        logger.info("Successfully updated target roles")
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    main()
