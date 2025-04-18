from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Table, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from pathlib import Path

Base = declarative_base()
engine = create_engine(f'sqlite:///{Path(__file__).parent.parent}/career_data.db')
Session = sessionmaker(bind=engine)

# Association table for experience-skill many-to-many relationship
experience_skills = Table(
    'experience_skills', Base.metadata,
    Column('experience_id', Integer, ForeignKey('experiences.id')),
    Column('skill_id', Integer, ForeignKey('skills.id'))
)

class Experience(Base):
    __tablename__ = 'experiences'
    
    id = Column(Integer, primary_key=True)
    company = Column(String)
    title = Column(String)
    start_date = Column(String)
    end_date = Column(String)
    description = Column(Text)
    
    skills = relationship('Skill', secondary=experience_skills, back_populates='experiences')

class Skill(Base):
    __tablename__ = 'skills'
    
    id = Column(Integer, primary_key=True)
    skill_name = Column(String, unique=True)
    
    experiences = relationship('Experience', secondary=experience_skills, back_populates='skills')

class TargetRole(Base):
    __tablename__ = 'target_roles'
    
    id = Column(Integer, primary_key=True)
    role_name = Column(String, unique=True)
    priority = Column(Integer)
    match_score = Column(Float)
    reasoning = Column(Text)
    source = Column(String)
    last_updated = Column(String)

class ResumeSection(Base):
    __tablename__ = 'resume_sections'
    
    id = Column(Integer, primary_key=True)
    section_name = Column(String, unique=True)
    content = Column(Text)

class ResumeExperience(Base):
    __tablename__ = 'resume_experience'
    
    id = Column(Integer, primary_key=True)
    company = Column(String)
    title = Column(String)
    start_date = Column(String)
    end_date = Column(String)
    location = Column(String)
    description = Column(Text)

class ResumeEducation(Base):
    __tablename__ = 'resume_education'
    
    id = Column(Integer, primary_key=True)
    institution = Column(String)
    degree = Column(String)
    field = Column(String)
    graduation_date = Column(String)
    gpa = Column(String)

class CoverLetterSection(Base):
    __tablename__ = 'cover_letter_sections'
    
    id = Column(Integer, primary_key=True)
    section_name = Column(String, unique=True)
    content = Column(Text)

class JobCache(Base):
    __tablename__ = 'job_cache'
    
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, index=True)
    title = Column(String)
    company = Column(String)
    description = Column(Text)
    first_seen_date = Column(String)
    last_seen_date = Column(String)
    match_score = Column(Float)
    application_priority = Column(String)
    key_requirements = Column(Text)
    culture_indicators = Column(Text)
    career_growth_potential = Column(String)
    search_query = Column(String)
    
    applications = relationship('JobApplication', back_populates='job')

class JobApplication(Base):
    __tablename__ = 'job_applications'
    
    id = Column(Integer, primary_key=True)
    job_cache_id = Column(Integer, ForeignKey('job_cache.id'))
    application_date = Column(String, index=True)
    status = Column(String)
    resume_path = Column(String)
    cover_letter_path = Column(String)
    notes = Column(Text)
    
    job = relationship('JobCache', back_populates='applications')