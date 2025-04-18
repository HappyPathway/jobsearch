from pathlib import Path
from utils import setup_logging
from models import Base, engine

logger = setup_logging('init_db')

def init_database():
    """Initialize all database tables"""
    logger.info("Initializing/updating database schema")
    try:
        # Create all tables defined in models.py
        Base.metadata.create_all(engine)
        logger.info("Database schema update complete")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def main():
    try:
        init_database()
        print("Database initialization check complete")
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    main()