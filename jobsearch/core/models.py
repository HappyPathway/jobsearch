import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Table, Text, event, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, Session
from contextlib import contextmanager
from jobsearch.core.storage import GCSManager
from jobsearch.core.logging_utils import setup_logging

logger = setup_logging('models')
gcs = GCSManager()

Base = declarative_base()

def create_tables_if_missing(engine):
    """Create missing tables in the database"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                logger.info(f"Creating missing table: {table.name}")
                table.create(conn)

def check_and_update_schema(engine):
    """Check if all columns exist and add missing ones"""
    inspector = inspect(engine)
    create_tables_if_missing(engine)
    
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing_columns = {col['name'] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing_columns:
                    # SQLite doesn't support ALTER TABLE ADD COLUMN with constraints
                    # So we need to handle defaults and nullable differently
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

def get_engine():
    """Get SQLAlchemy engine with latest database from GCS"""
    gcs.sync_db()  # Just sync, don't handle locks
    engine = create_engine(f'sqlite:///{gcs.local_db_path}')
    check_and_update_schema(engine)
    return engine

engine = get_engine()
SessionFactory = sessionmaker(bind=engine)

@contextmanager
def get_session():
    """Session context manager that handles GCS sync and locking"""
    if not gcs.acquire_lock():
        raise Exception("Could not acquire database lock")
    try:
        gcs.sync_db()  # Sync after acquiring lock
        session = SessionFactory()
        try:
            yield session
            session.commit()
            # Upload to GCS after successful commit
            blob = gcs.bucket.blob(gcs.db_blob_name)
            blob.upload_from_filename(gcs.local_db_path)
        except:
            session.rollback()
            raise
        finally:
            session.close()
    finally:
        gcs.release_lock()  # Always release lock

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
    requirements = Column(Text)  # JSON array of requirements
    next_steps = Column(Text)  # JSON array of action items

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
    location = Column(String)
    post_date = Column(String)
    first_seen_date = Column(String)
    last_seen_date = Column(String)
    match_score = Column(Float)
    application_priority = Column(String)
    key_requirements = Column(Text)  # JSON array
    culture_indicators = Column(Text)  # JSON array
    career_growth_potential = Column(String)
    search_query = Column(String)
    
    # New fields for enhanced analysis
    total_years_experience = Column(Integer, default=0)
    candidate_gaps = Column(Text)  # JSON array
    location_type = Column(String, default='unknown')  # remote|hybrid|onsite
    
    # Company overview fields
    company_size = Column(String)  # startup|midsize|large|enterprise
    company_stability = Column(String)  # high|medium|low
    glassdoor_rating = Column(String)
    employee_count = Column(String)
    year_founded = Column(String)
    growth_stage = Column(String)  # early|growth|mature|declining
    market_position = Column(String)  # leader|challenger|follower
    development_opportunities = Column(Text)  # JSON array
    
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