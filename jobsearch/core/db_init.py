"""Database initialization and management using core components."""
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from sqlalchemy import inspect, text

from jobsearch.core.logging import setup_logging
from jobsearch.core.storage import GCSManager
from jobsearch.core.monitoring import setup_monitoring
from jobsearch.core.database import (
    Base, get_engine, Experience, Skill, 
    TargetRole, JobCache, JobApplication,
    ResumeSection, CoverLetterSection
)

# Initialize core components
logger = setup_logging('init_db')
storage = GCSManager()
monitoring = setup_monitoring('database')

def init_database() -> bool:
    """Initialize all database tables and sync with GCS."""
    try:
        monitoring.increment('database_init')
        
        # Create database engine
        engine = get_engine()
        
        # Create all tables
        logger.info("Creating database tables")
        Base.metadata.create_all(engine)
        
        # Sync with GCS
        logger.info("Syncing database with Google Cloud Storage")
        storage.sync_db()
        
        monitoring.track_success('database_init')
        logger.info("Successfully initialized database")
        return True
        
    except Exception as e:
        monitoring.track_error('database_init', str(e))
        logger.error(f"Error initializing database: {str(e)}")
        return False

def validate_schema() -> bool:
    """Validate database schema and relationships."""
    try:
        monitoring.increment('validate_schema')
        engine = get_engine()
        
        # Test table creation and relationships
        Base.metadata.create_all(engine)
        
        # Test basic model operations
        from jobsearch.core.database import get_session
        
        with get_session() as session:
            # Test experience-skill relationship
            exp = Experience(
                company="Test Company",
                title="Test Role",
                start_date="2025-01",
                end_date="2025-04",
                description="Test description"
            )
            skill = Skill(skill_name="Test Skill")
            exp.skills.append(skill)
            session.add_all([exp, skill])
            
            # Test target role
            role = TargetRole(
                role_name="Test Role",
                priority=1,
                match_score=0.9,
                reasoning="Test reasoning",
                source="test",
                last_updated=datetime.now().isoformat(),
                requirements=[],
                next_steps=[]
            )
            session.add(role)
            
            # Test job cache and application
            job = JobCache(
                url="http://test.com/job",
                title="Test Job",
                company="Test Company",
                location="Remote",
                description="Test description",
                first_seen_date=datetime.now().isoformat(),
                last_seen_date=datetime.now().isoformat(),
                key_requirements=[],
                culture_indicators=[],
                career_growth_potential="high",
                total_years_experience=5,
                candidate_gaps=[],
                location_type="remote",
                company_size="startup",
                company_stability="stable",
                glassdoor_rating="4.5",
                employee_count="100-500",
                industry="Technology",
                funding_stage="Series B",
                benefits=[],
                tech_stack=[]
            )
            session.add(job)
            
            # Test document sections
            resume_section = ResumeSection(
                section_type="summary",
                title="Professional Summary",
                content="Test content",
                order=1
            )
            cover_letter_section = CoverLetterSection(
                section_type="opener",
                content_template="Test template",
                style_notes="Test notes",
                tone="professional"
            )
            session.add_all([resume_section, cover_letter_section])
            
            # Commit to test constraints
            session.commit()
            
            # Clean up test data
            session.delete(exp)
            session.delete(skill)
            session.delete(role)
            session.delete(job)
            session.delete(resume_section)
            session.delete(cover_letter_section)
            session.commit()
            
        monitoring.track_success('validate_schema')
        logger.info("Successfully validated database schema")
        return True
        
    except Exception as e:
        monitoring.track_error('validate_schema', str(e))
        logger.error(f"Error validating schema: {str(e)}")
        return False

def cleanup_database() -> bool:
    """Clean up old data and optimize the database."""
    try:
        monitoring.increment('cleanup_database')
        engine = get_engine()
        
        with engine.begin() as conn:
            # Vacuum database to reclaim space
            conn.execute(text("VACUUM"))
            
            # Analyze tables for query optimization
            conn.execute(text("ANALYZE"))
            
        monitoring.track_success('cleanup_database')
        logger.info("Successfully cleaned up database")
        return True
        
    except Exception as e:
        monitoring.track_error('cleanup_database', str(e))
        logger.error(f"Error cleaning up database: {str(e)}")
        return False

def main() -> int:
    """Main entry point."""
    try:
        # Initialize database
        if not init_database():
            logger.error("Failed to initialize database")
            return 1
            
        # Validate schema
        if not validate_schema():
            logger.error("Failed to validate database schema")
            return 1
            
        # Clean up and optimize
        if not cleanup_database():
            logger.warning("Database cleanup failed but continuing")
            
        logger.info("Database initialization complete")
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error in database initialization: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())