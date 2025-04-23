from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List
from sqlalchemy.orm import Session

from ..models.profile import (
    SkillCreate, SkillResponse, ExperienceCreate, 
    ExperienceResponse, ProfileSummary, ProfileUpdate
)
from ..dependencies import get_db, get_current_user, storage

# Import from installed package
from jobsearch.core.models import Experience, Skill
from jobsearch.features.profile_management.parser import (
    extract_text_from_pdf,
    parse_profile_text,
    save_profile_data
)

router = APIRouter()

@router.get("/summary", response_model=ProfileSummary)
async def get_profile_summary(db: Session = Depends(get_db)):
    """Get profile summary including skills and experiences"""
    # Get top skills ordered by years of experience
    skills = db.query(Skill).order_by(Skill.years_experience.desc()).limit(10).all()
    
    # Get most recent experiences
    experiences = (
        db.query(Experience)
        .order_by(Experience.start_date.desc())
        .limit(5)
        .all()
    )
    
    return ProfileSummary(
        target_roles=["Cloud Architect", "DevOps Engineer", "Infrastructure Engineer"],
        top_skills=skills,
        recent_experiences=experiences
    )

@router.post("/skills", response_model=SkillResponse)
async def create_skill(
    skill: SkillCreate,
    db: Session = Depends(get_db)
):
    """Add a new skill to the profile"""
    db_skill = Skill(**skill.model_dump())
    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)
    return db_skill

@router.get("/skills", response_model=List[SkillResponse])
async def list_skills(db: Session = Depends(get_db)):
    """List all skills"""
    return db.query(Skill).all()

@router.post("/experiences", response_model=ExperienceResponse)
async def create_experience(
    experience: ExperienceCreate,
    db: Session = Depends(get_db)
):
    """Add a new experience entry"""
    # Create experience
    exp_data = experience.model_dump(exclude={'skills'})
    db_experience = Experience(**exp_data)
    db.add(db_experience)
    db.commit()
    
    # Add skills
    for skill_name in experience.skills:
        skill = db.query(Skill).filter(Skill.name == skill_name).first()
        if skill:
            db_experience.skills.append(skill)
    
    db.commit()
    db.refresh(db_experience)
    return db_experience

@router.get("/experiences", response_model=List[ExperienceResponse])
async def list_experiences(db: Session = Depends(get_db)):
    """List all experiences"""
    return db.query(Experience).all()

@router.post("/upload/resume")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and parse a resume file"""
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as temp_file:
            content = await file.read()
            temp_file.write(content)
        
        # Extract and parse text
        text = extract_text_from_pdf(temp_path)
        parsed_data = parse_profile_text(text)
        
        # Save to database
        save_profile_data(parsed_data, db)
        
        # Upload to GCS
        gcs_path = f"resumes/{file.filename}"
        storage.upload_file(temp_path, gcs_path)
        
        return {"status": "success", "message": "Resume processed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))