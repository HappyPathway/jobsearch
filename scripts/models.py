from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Table, Text, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from pathlib import Path
from contextlib import contextmanager
from gcs_utils import gcs
from logging_utils import setup_logging

logger = setup_logging('models')

Base = declarative_base()

def get_engine():
    """Get SQLAlchemy engine with latest database from GCS"""
    gcs.sync_db()
    return create_engine(f'sqlite:///{gcs.local_db_path}')

engine = get_engine()
SessionFactory = sessionmaker(bind=engine)

@contextmanager
def get_session():
    """Session context manager that syncs with GCS"""
    session = SessionFactory()
    try:
        yield session
        session.commit()
        # Upload to GCS after successful commit
        gcs.upload_db()
    except:
        session.rollback()
        raise
    finally:
        session.close()

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
    calendar_events = relationship('CalendarEvent', back_populates='job_application')

class CalendarEvent(Base):
    __tablename__ = 'calendar_events'
    
    id = Column(Integer, primary_key=True)
    job_application_id = Column(Integer, ForeignKey('job_applications.id'))
    event_type = Column(String)  # 'interview', 'follow_up', etc.
    start_time = Column(String)
    end_time = Column(String)
    description = Column(Text)
    location = Column(String)
    calendar_event_id = Column(String)  # ID from external calendar service
    provider = Column(String)  # 'google', 'local', etc.
    created_at = Column(String, default=lambda: datetime.now().isoformat())
    
    job_application = relationship('JobApplication', back_populates='calendar_events')

class RecruiterContact(Base):
    __tablename__ = 'recruiter_contacts'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    title = Column(String)
    company = Column(String, index=True)
    url = Column(String, unique=True)
    source = Column(String)
    found_date = Column(String)
    contacted_date = Column(String, nullable=True)
    status = Column(String, default='identified')  # identified, contacted, responded, scheduled, closed
    notes = Column(Text, nullable=True)

class EmailCorrespondence(Base):
    __tablename__ = 'email_correspondence'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('job_cache.id'))
    direction = Column(String)  # 'incoming' or 'outgoing'
    sender = Column(String)
    recipients = Column(String)  # JSON list
    subject = Column(String)
    body = Column(Text)
    received_date = Column(String, nullable=True)
    sent_date = Column(String, nullable=True)
    thread_id = Column(String, nullable=True)
    status = Column(String, default='unread')  # unread, read, archived
    has_calendar_invite = Column(String, default=False)
    processed_calendar = Column(String, default=False)
    
    job = relationship('JobCache')