import sqlite3
from pathlib import Path
from utils import setup_logging

logger = setup_logging('init_db')

def init_database():
    """Initialize all database tables"""
    db_path = Path(__file__).parent.parent / 'career_data.db'
    logger.info("Initializing/updating database schema")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Profile tables
    c.execute('''CREATE TABLE IF NOT EXISTS experiences (
        id INTEGER PRIMARY KEY,
        company TEXT,
        title TEXT,
        start_date TEXT,
        end_date TEXT,
        description TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY,
        skill_name TEXT UNIQUE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS experience_skills (
        experience_id INTEGER,
        skill_id INTEGER,
        FOREIGN KEY (experience_id) REFERENCES experiences (id),
        FOREIGN KEY (skill_id) REFERENCES skills (id)
    )''')
    
    # Target roles table
    c.execute('''CREATE TABLE IF NOT EXISTS target_roles (
        id INTEGER PRIMARY KEY,
        role_name TEXT UNIQUE,
        priority INTEGER,
        match_score REAL,
        reasoning TEXT,
        source TEXT,
        last_updated TEXT
    )''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_target_roles_priority ON target_roles(priority)''')
    
    # Resume tables
    c.execute('''CREATE TABLE IF NOT EXISTS resume_sections (
        id INTEGER PRIMARY KEY,
        section_name TEXT UNIQUE,
        content TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS resume_experience (
        id INTEGER PRIMARY KEY,
        company TEXT,
        title TEXT,
        start_date TEXT,
        end_date TEXT,
        location TEXT,
        description TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS resume_education (
        id INTEGER PRIMARY KEY,
        institution TEXT,
        degree TEXT,
        field TEXT,
        graduation_date TEXT,
        gpa TEXT
    )''')
    
    # Cover letter tables
    c.execute('''CREATE TABLE IF NOT EXISTS cover_letter_sections (
        id INTEGER PRIMARY KEY,
        section_name TEXT UNIQUE,
        content TEXT
    )''')
    
    # Job cache and tracking tables
    c.execute('''CREATE TABLE IF NOT EXISTS job_cache (
        id INTEGER PRIMARY KEY,
        url TEXT UNIQUE,
        title TEXT,
        company TEXT,
        description TEXT,
        first_seen_date TEXT,
        last_seen_date TEXT,
        match_score REAL,
        application_priority TEXT,
        key_requirements TEXT,
        culture_indicators TEXT,
        career_growth_potential TEXT,
        search_query TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS job_applications (
        id INTEGER PRIMARY KEY,
        job_cache_id INTEGER,
        application_date TEXT,
        status TEXT,
        resume_path TEXT,
        cover_letter_path TEXT,
        notes TEXT,
        FOREIGN KEY (job_cache_id) REFERENCES job_cache (id)
    )''')
    
    c.execute('''CREATE INDEX IF NOT EXISTS idx_job_cache_url ON job_cache(url)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_job_applications_date ON job_applications(application_date)''')
    
    conn.commit()
    logger.info("Database schema update complete")
    return conn

def main():
    try:
        init_database()
        print("Database initialization check complete")
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    main()