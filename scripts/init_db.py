import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.gcs_utils import GCSManager as gcs
from scripts.models import Base, get_engine
from logging_utils import setup_logging

logger = setup_logging('init_db')

def init_database():
    """Initialize all database tables and sync with GCS"""
    logger.info("Initializing/updating database schema")
    try:
        # Create all tables defined in models.py
        Base.metadata.create_all(get_engine())
        
        # Upload fresh database to GCS
        gcs_manager = gcs()
        if gcs_manager.upload_db():
            logger.info("Successfully uploaded initial database to GCS")
        else:
            logger.warning("Failed to upload initial database to GCS")
            
        logger.info("Database schema update complete")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def main():
    try:
        init_database()
        print("Database initialization and GCS sync complete")
    except Exception as e:
        print(f"Error initializing database: {e}")
        exit(1)

if __name__ == "__main__":
    main()