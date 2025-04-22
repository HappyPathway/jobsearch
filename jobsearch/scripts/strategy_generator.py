"""Job search strategy generation and planning."""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import google.generativeai as genai
from dotenv import load_dotenv

from ..core.ai import StructuredPrompt
from ..core.logging import setup_logging
from ..core.database import (
    Experience, Skill, TargetRole, JobCache, 
    JobApplication, get_session
)
from ..core.storage import gcs
from .common import JobInfo, get_today

logger = setup_logging('strategy_generator')

# Configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_profile_summary() -> Dict:
    """Get summarized profile data from database"""
    with get_session() as session:
        experiences = []
        skills = set()
        
        # Get experiences and skills
        for exp in session.query(Experience).all():
            experiences.append({
                'company': exp.company,
                'title': exp.title,
                'start_date': exp.start_date,
                'end_date': exp.end_date,
                'description': exp.description,
                'skills': [skill.skill_name for skill in exp.skills]
            })
            for skill in exp.skills:
                skills.add(skill.skill_name)
                
        # Get target roles
        target_roles = []
        for role in session.query(TargetRole).all():
            target_roles.append({
                'role_name': role.role_name,
                'priority': role.priority,
                'match_score': role.match_score,
                'requirements': json.loads(role.requirements) if role.requirements else [],
                'next_steps': json.loads(role.next_steps) if role.next_steps else []
            })
            
        return {
            'experiences': experiences,
            'skills': list(skills),
            'target_roles': target_roles
        }

def get_recent_applications() -> List[Dict]:
    """Get recent job applications from database"""
    with get_session() as session:
        applications = []
        for app in session.query(JobApplication).order_by(
            JobApplication.application_date.desc()
        ).limit(10):
            applications.append({
                'company': app.job.company,
                'title': app.job.title,
                'date': app.application_date,
                'status': app.status
            })
        return applications

def get_high_priority_jobs() -> List[Dict]:
    """Get high priority jobs from database"""
    with get_session() as session:
        jobs = []
        for job in session.query(JobCache).filter(
            JobCache.application_priority == 'high'
        ).order_by(JobCache.match_score.desc()).all():
            jobs.append({
                'url': job.url,
                'title': job.title,
                'company': job.company,
                'match_score': job.match_score,
                'key_requirements': json.loads(job.key_requirements) if job.key_requirements else [],
                'culture_indicators': json.loads(job.culture_indicators) if job.culture_indicators else [],
                'career_growth_potential': job.career_growth_potential
            })
        return jobs

def generate_daily_strategy(profile_data: Dict, recent_applications: List[Dict], priority_jobs: List[Dict]) -> Optional[Dict]:
    """Generate daily job search strategy using Gemini"""
    try:
        structured_prompt = StructuredPrompt()
        
        expected_structure = {
            "daily_focus": {
                "primary_goal": str,
                "secondary_goals": [str]
            },
            "target_companies": [str],
            "skill_development": {
                "focus_areas": [str],
                "resources": [str]
            },
            "networking": {
                "target_roles": [str],
                "outreach_templates": [str],
                "connection_targets": int
            },
            "success_metrics": {
                "applications_target": int,
                "networking_messages": int,
                "skill_development_hours": int
            },
            "schedule": {
                "morning": [str],
                "afternoon": [str],
                "evening": [str]
            },
            "priorities": {
                "immediate": [str],
                "short_term": [str],
                "long_term": [str]
            }
        }
        
        example_data = {
            "daily_focus": {
                "primary_goal": "Apply to 3 high-priority cloud engineering roles",
                "secondary_goals": [
                    "Complete AWS certification practice exam",
                    "Follow up on pending applications"
                ]
            },
            "target_companies": [
                "Example Tech Co",
                "Innovation Labs",
                "Cloud Services Inc"
            ],
            "skill_development": {
                "focus_areas": ["Kubernetes", "Terraform", "AWS"],
                "resources": [
                    "Kubernetes certification course",
                    "Infrastructure as Code workshop"
                ]
            },
            "networking": {
                "target_roles": [
                    "Cloud Engineer",
                    "DevOps Engineer",
                    "Platform Engineer"
                ],
                "outreach_templates": [
                    "Hi [Name], I noticed your work in cloud infrastructure...",
                    "Hello [Name], I'm interested in learning more about..."
                ],
                "connection_targets": 5
            },
            "success_metrics": {
                "applications_target": 3,
                "networking_messages": 5,
                "skill_development_hours": 2
            },
            "schedule": {
                "morning": [
                    "Review job boards and apply to priority roles",
                    "Update application tracking"
                ],
                "afternoon": [
                    "Technical skill development",
                    "Work on certification"
                ],
                "evening": [
                    "Networking outreach",
                    "Follow up on applications"
                ]
            },
            "priorities": {
                "immediate": [
                    "Apply to identified high-priority roles",
                    "Follow up on pending applications"
                ],
                "short_term": [
                    "Complete cloud certification",
                    "Build portfolio project"
                ],
                "long_term": [
                    "Transition to senior role",
                    "Expand professional network"
                ]
            }
        }

        strategy = structured_prompt.get_structured_response(
            prompt=f"""Generate a daily job search strategy based on profile data and recent activity.
Consider target roles, skill gaps, and high-priority opportunities.

Profile Summary:
{json.dumps(profile_data, indent=2)}

Recent Applications:
{json.dumps(recent_applications, indent=2)}

Priority Jobs:
{json.dumps(priority_jobs, indent=2)}

Generate a structured strategy that includes:
1. Daily focus and goals
2. Target companies to research
3. Skill development plan
4. Networking strategy
5. Success metrics
6. Daily schedule
7. Short and long-term priorities

Return only the structured JSON response.""",
            expected_structure=expected_structure,
            example_data=example_data,
            temperature=0.3
        )

        if strategy:
            logger.info("Successfully generated daily strategy")
            return strategy
        else:
            logger.error("Failed to generate strategy")
            return None

    except Exception as e:
        logger.error(f"Error generating strategy: {str(e)}")
        return None

def store_strategy(strategy: Dict) -> bool:
    """Store strategy in GCS"""
    try:
        today = get_today()
        gcs_path = f'strategies/{today}_strategy.json'
        
        return gcs.safe_upload(json.dumps(strategy, indent=2), gcs_path)
        
    except Exception as e:
        logger.error(f"Error storing strategy: {str(e)}")
        return False

def generate_strategy() -> Dict:
    """Generate and store daily job search strategy"""
    try:
        # Get required data
        profile_data = get_profile_summary()
        recent_applications = get_recent_applications()
        priority_jobs = get_high_priority_jobs()
        
        # Generate strategy
        strategy = generate_daily_strategy(
            profile_data=profile_data,
            recent_applications=recent_applications,
            priority_jobs=priority_jobs
        )
        
        if not strategy:
            return {'success': False, 'error': 'Failed to generate strategy'}
            
        # Store strategy
        if not store_strategy(strategy):
            return {'success': False, 'error': 'Failed to store strategy'}
            
        return {
            'success': True,
            'strategy': strategy
        }
        
    except Exception as e:
        logger.error(f"Error in strategy generation: {str(e)}")
        return {'success': False, 'error': str(e)}