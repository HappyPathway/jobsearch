"""SQLAlchemy models for job search functionality."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, Table, Text, inspect, text
from sqlalchemy.orm import relationship, mapped_column, Mapped
from pathlib import Path

from jobsearch.core.logging import setup_logging
from jobsearch.core.database import Base
from jobsearch.core.storage import GCSManager
from jobsearch.core.monitoring import setup_monitoring

# Initialize core components
logger = setup_logging('core_models')
storage = GCSManager()
monitoring = setup_monitoring('models')

def create_tables_if_missing(engine):
    """Create missing tables in the database."""
    try:
        monitoring.increment('create_tables')
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                if table.name not in existing_tables:
                    logger.info(f"Creating missing table: {table.name}")
                    table.create(conn)
                    
        monitoring.track_success('create_tables')
        
    except Exception as e:
        monitoring.track_error('create_tables', str(e))
        logger.error(f"Error creating tables: {str(e)}")
        raise

def check_and_update_schema(engine):
    """Check if all columns exist and add missing ones."""
    try:
        monitoring.increment('check_schema')
        inspector = inspect(engine)
        create_tables_if_missing(engine)
        
        with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                existing_columns = {col['name'] for col in inspector.get_columns(table.name)}
                for column in table.columns:
                    if column.name not in existing_columns:
                        column_type = column.type.compile(engine.dialect)
                        
                        # Handle default values for existing rows
                        default_value = "NULL"
                        if column.default is not None:
                            if isinstance(column.default.arg, str):
                                default_value = f"'{column.default.arg}'"
                            else:
                                default_value = str(column.default.arg)
                        elif not column.nullable:
                            if isinstance(column.type, String):
                                default_value = "''"
                            elif isinstance(column.type, (Integer, Float)):
                                default_value = "0"
                            else:
                                default_value = "NULL"
                                
                        # SQLite specific ALTER TABLE
                        sql = text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type} DEFAULT {default_value}")
                        
                        try:
                            conn.execute(sql)
                            # Remove the default constraint if it wasn't originally specified
                            if column.default is None and not column.nullable:
                                update_sql = text(f"UPDATE {table.name} SET {column.name} = {default_value}")
                                conn.execute(update_sql)
                            logger.info(f"Added column {column.name} to table {table.name}")
                            
                        except Exception as e:
                            logger.error(f"Error adding column {column.name} to {table.name}: {str(e)}")
                            raise
                            
        monitoring.track_success('check_schema')
        
    except Exception as e:
        monitoring.track_error('check_schema', str(e))
        logger.error(f"Error checking schema: {str(e)}")
        raise

# Association table for many-to-many relationships
experience_skills = Table(
    'experience_skills', Base.metadata,
    Column('experience_id', Integer, ForeignKey('experiences.id')),
    Column('skill_id', Integer, ForeignKey('skills.id'))
)

class Experience(Base):
    """Model for work experiences."""
    __tablename__ = 'experiences'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str]
    title: Mapped[str]
    start_date: Mapped[str]
    end_date: Mapped[str]
    description: Mapped[str]
    
    skills = relationship('Skill', secondary=experience_skills, back_populates='experiences')
    
class Skill(Base):
    """Model for professional skills."""
    __tablename__ = 'skills'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    skill_name: Mapped[str] = mapped_column(unique=True)
    
    experiences = relationship('Experience', secondary=experience_skills, back_populates='skills')
    
class TargetRole(Base):
    """Model for target career roles."""
    __tablename__ = 'target_roles'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    role_name: Mapped[str] = mapped_column(unique=True)
    priority: Mapped[int]
    match_score: Mapped[float]
    reasoning: Mapped[str] = mapped_column(Text)
    source: Mapped[str]
    last_updated: Mapped[str]
    requirements: Mapped[str] = mapped_column(JSON)
    next_steps: Mapped[str] = mapped_column(JSON)
    
class ResumeSection(Base):
    """Model for resume content sections."""
    __tablename__ = 'resume_sections'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    section_type: Mapped[str]  # summary, experience, education, skills
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    order: Mapped[int]
    
class ResumeExperience(Base):
    """Model for tailored experience summaries."""
    __tablename__ = 'resume_experience'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    experience_id: Mapped[int] = mapped_column(ForeignKey('experiences.id'))
    role_id: Mapped[int] = mapped_column(ForeignKey('target_roles.id'))
    tailored_description: Mapped[str] = mapped_column(Text)
    
class ResumeEducation(Base):
    """Model for education entries."""
    __tablename__ = 'resume_education'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    institution: Mapped[str]
    degree: Mapped[str]
    field: Mapped[str]
    start_date: Mapped[str]
    end_date: Mapped[str]
    description: Mapped[Optional[str]] = mapped_column(Text)
    
class CoverLetterSection(Base):
    """Model for cover letter sections."""
    __tablename__ = 'cover_letter_sections'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    section_type: Mapped[str]  # opener, body, closing
    content_template: Mapped[str] = mapped_column(Text)
    style_notes: Mapped[str] = mapped_column(Text)
    tone: Mapped[str]
    
class JobCache(Base):
    """Model for job postings and analysis."""
    __tablename__ = 'job_cache'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(unique=True, index=True)
    title: Mapped[str]
    company: Mapped[str]
    location: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    post_date: Mapped[Optional[str]]
    first_seen_date: Mapped[str]
    last_seen_date: Mapped[str]
    search_query: Mapped[Optional[str]]
    
    # Analysis fields
    match_score: Mapped[Optional[float]]
    key_requirements: Mapped[List[str]] = mapped_column(JSON)
    culture_indicators: Mapped[List[str]] = mapped_column(JSON)
    career_growth_potential: Mapped[str]
    total_years_experience: Mapped[int]
    candidate_gaps: Mapped[List[str]] = mapped_column(JSON)
    location_type: Mapped[str]
    
    # Company analysis fields
    company_size: Mapped[str]
    company_stability: Mapped[str]
    glassdoor_rating: Mapped[str]
    employee_count: Mapped[str]
    industry: Mapped[str]
    funding_stage: Mapped[str]
    benefits: Mapped[List[str]] = mapped_column(JSON)
    tech_stack: Mapped[List[str]] = mapped_column(JSON)
    
    applications = relationship('JobApplication', back_populates='job')
    
class JobApplication(Base):
    """Model for job application tracking."""
    __tablename__ = 'job_applications'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    job_cache_id: Mapped[int] = mapped_column(ForeignKey('job_cache.id'))
    application_date: Mapped[str] = mapped_column(index=True)
    status: Mapped[str]  # applied, interviewing, rejected, accepted
    resume_path: Mapped[str]  # GCS path
    cover_letter_path: Mapped[str]  # GCS path
    notes: Mapped[str] = mapped_column(Text)
    
    job = relationship('JobCache', back_populates='applications')
    contacts = relationship('RecruiterContact', back_populates='application')
    
class RecruiterContact(Base):
    """Model for tracking recruiter interactions."""
    __tablename__ = 'recruiter_contacts'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[Optional[int]] = mapped_column(ForeignKey('job_applications.id'))
    name: Mapped[str]
    title: Mapped[str]
    company: Mapped[str] = mapped_column(index=True)
    email: Mapped[Optional[str]]
    linkedin_url: Mapped[Optional[str]]
    source: Mapped[str]
    found_date: Mapped[str]
    last_contact_date: Mapped[Optional[str]]
    status: Mapped[str]  # identified, contacted, responded, scheduled, closed
    notes: Mapped[str] = mapped_column(Text)
    
    application = relationship('JobApplication', back_populates='contacts')